import logging

from typing import Optional
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from prometheus_client import Counter

from status_bot.constants import EventTypeEnum, NotificationCategoryEnum
from status_bot.models import FeedbackMessage, ContactRequest
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.utils import download_image, extract_contact_request, download_image
from status_bot.exceptions import ImageDownloadFailedException
from status_sdk import GroupChat

logger = logging.getLogger(__name__)

MANDATORY_CONFIG_FIELD = [
    # Events Config
    "first_messages", "feedback_keywords","helper_message", "automatic_reply", "group_chat",
    "new_user_message_contact_request", "existing_users_messages", "image_folder",
    # Periodic Config
    "periodic_messages"
]

REPLY_MSG_ERROR_IMG = "\nAn image was sent, but an error occured during the download"

IGNORED_MSG_CONTENT_TYPE = [
    11, # Contact request
    15, # Send contact request
    17  # Removed Contact
]

def get_all_contact_to_contact(db_session, delay, delay_unit):
    threshold = datetime.now() - timedelta(days=delay)
    if delay_unit != "days":
        threshold = datetime.utcnow() - timedelta(minutes=delay)
    logger.info(f"Threshold {threshold}")

    return db_session.query(ContactRequest).filter(
        and_(
            ContactRequest.request_timestamp < threshold,
            ContactRequest.last_engagement_message < delay,
            ContactRequest.is_new_user
        )
    ).all()

def get_response_reply_if_exist(db_session, messages) -> Optional[str]:
    msg_response_to = next(
       (msg["responseTo"] for msg in messages if "responseTo" in msg),
        None
    )
    if msg_response_to:
        logger.debug(f"replying to message {msg_response_to}")
        reply_to = db_session.query(FeedbackMessage).filter(FeedbackMessage.reply_chat_id==msg_response_to).first()
        logger.debug(f"Original Message here {reply_to}")
        if reply_to:
            return reply_to.reply_chat_id

    return None

class Engagement(BaseModule):

    DESCRIPTION = """
        Module made for Engagmement in the Status App.
        It accept all the friend request and send welcome message
    """

    @property
    def module_type(self) -> set[ModuleType]:
        return {ModuleType.EVENT, ModuleType.PERIODIC}

    def on_start(self):
        logger.info("Starting module Engagement Bot")
        self._verify_mandatory_config(MANDATORY_CONFIG_FIELD)
        if self.ctx.db is None:
            raise ConnectionError("Database connection not setup")
        group_chat_config=self.ctx.config.settings.get("group_chat", {})
        if not group_chat_config.get("group_id"):
            logger.debug("Initializing new GroupChat")
            contacts = [contact["public_key"] for contact in
                        self.ctx.account.contacts.values() if contact["compressed_key"]
                        in group_chat_config.get("participants")]
            for c in contacts:
                self.ctx.account.add_contact(c)
            logger.info(f"Creating group with {contacts}")
            self.group_chat = GroupChat(self.ctx.account).create(
                    public_keys=contacts,
                    name=group_chat_config.get("name"))
            logger.info(f"New Group {group_chat_config.get('name')} created: {self.group_chat.id}")
        else:
            logger.debug("Loading existing GroupChat")
            self.group_chat = GroupChat(
                    account=self.ctx.account,
                    chat_id=group_chat_config.get("group_id"))
        logger.info(f"The bot will detect messages with the following keywords {self.ctx.config.settings.get('feedback_keywords', [])}")


    """
    Function to handle new contact request.

    Parameters
    """
    def hanlde_contact_request(self, event_data: dict, db_session):
        new_contact: ContactRequest = extract_contact_request(
                event_data, self.ctx.config.settings.get("new_user_message_contact_request", ""))
        self._counter.labels(type="received_request").inc()
        logger.info(f"Accepting the contact request from {new_contact.public_key}")
        self.ctx.account.add_contact(new_contact.public_key)
        db_session.merge(new_contact)
        db_session.commit()
        self._counter.labels(type="accepted_request").inc()
        logger.info(f"Sending first message to {new_contact.public_key}")
        message_properties = "existing_users_messages"
        if new_contact.is_new_user:
            message_properties = "first_messages"
        for msg in self.ctx.config.settings.get(message_properties, []):
            self.ctx.account.send_message(
                chat_id=new_contact.public_key,
                message=msg)
        self._counter.labels(type=message_properties).inc()



    def extract_user_messages(self, messages: list[dict], ) -> list[dict]:
        """
            This function take the raw messages from the signal and remove the messages from
            the bot account.
            This help to remove reply content.

            Parameters:
                - messages: list of messages from the raw signals
                - bot_compressed_key key

            Output:
                - List of messages from the user
        """
        clean_msg_list = []
        for msg in messages:
            if msg.get("compressedKey") == self.ctx.account.info["compressed_key"]:
                continue
            if msg.get("text") == self.ctx.config.settings.get("new_user_message_contact_request"):
                continue
            if msg.get("contentType") in IGNORED_MSG_CONTENT_TYPE:
                continue
            clean_msg_list.append(msg)

        return clean_msg_list

    """
        Verify if the message concerne the feedback or is concidered spam.
        Use only the first message since multiple messages are image album
        and sahre the same text.
    """
    def is_feedback_message(self, messages) -> bool:
        feedback_keywords = self.ctx.config.settings.get("feedback_keywords", [])
        return any(kw in messages[0].get("text").lower() for kw in feedback_keywords)

    def send_message(self, chat_id: str, orignal_message: dict, msg_content: str, reply_id: Optional[str]):
        send_msg_id=None
        if orignal_message.get("image"):
            try:
                image_path=f"{self.ctx.config.settings.get('image_folder')}/{orignal_message.get('id')}"
                download_image(
                    url=orignal_message.get("image", "").replace('localhost', 'backend'),
                    image_path=image_path)
                send_msg_id = self.ctx.account.send_image(
                        chat_id=chat_id,
                        file_path=image_path,
                        message=msg_content,
                        reply_to_message_id=reply_id)
            except ImageDownloadFailedException as e:
                logger.error(e)
                send_msg_id = self.ctx.account.send_message(
                    chat_id=chat_id,
                    message=f"{msg_content} {REPLY_MSG_ERROR_IMG}",
                    reply_to_message_id=reply_id
                )
        else:
            send_msg_id = self.ctx.account.send_message(
                chat_id=chat_id,
                message=msg_content,
                reply_to_message_id=reply_id)

        return send_msg_id


    """
        Manage message sent to the Bot by a User
    """
    def handle_users_messages(self, messages: list[dict], db_session):
        user_public_key = messages[0].get("from")
        message_id = messages[0].get("id")
        reply_id = get_response_reply_if_exist(db_session, messages)
        if not self.is_feedback_message(messages) and not reply_id:
            logger.info("Not matching the feedback keywords")
            self.ctx.account.send_message(
                chat_id=user_public_key,
                message=self.ctx.config.settings.get("helper_message"),
                reply_to_message_id=message_id)
            self._counter.labels(type="invalid-feedback-query").inc()
            return

        logger.info(f"A new feedback message has been received from {user_public_key}")
        self.ctx.account.send_message(
                chat_id=user_public_key,
                message=self.ctx.config.settings.get("automatic_reply"),
                reply_to_message_id=message_id)
        self._counter.labels(type="valid-feedback-query").inc()


        first_msg = True
        for msg in messages:
            request_text = msg.get("text", "")
            if not first_msg:
                # If the message is another photo of the album we don't send the text again
                request_text = ""
            if first_msg and not reply_id:
                # sending the config message only for the first message of a feedback
                # request, not for reply or for other photos
                self.group_chat.send_message(
                    message=self.ctx.config.settings.get("group_message_text"))

            msg_id = self.send_message(self.group_chat.id, msg, request_text, reply_id)

            feedback_message: FeedbackMessage = FeedbackMessage(
                id=message_id,
                public_key=user_public_key,
                request_message=messages[0].get("text"),
                request_timestamp=messages[0].get("timestamp"),
                chat_id=messages[0].get("chatId"),
                group_chat_message_id=msg_id)
            logger.debug(f"Sending the request {feedback_message.id} to ChatGroup")

            db_session.merge(feedback_message)
            db_session.commit()
        self._counter.labels(type="request-transfered").inc()

    """
        Manage messages sent by the GroupChat to be transfert to the users
    """
    def find_reply(self, messages: list[dict], db_session):
        responseTo = messages[0].get("responseTo")
        if responseTo is None or responseTo == "":
            logger.debug("The message isn't a reply, ignoring it")
            return
        original_message: FeedbackMessage = db_session.query(FeedbackMessage).filter(FeedbackMessage.group_chat_message_id==responseTo).first()
        if original_message == None:
            logger.warning(f"No original message found for id {responseTo}")
            self._counter.labels(type="original-not-found").inc()
            return
        logger.debug(f"Sending reply to message {original_message.id}")
        reply_content = messages[0].get("text", "")
        reply_id: str = ""
        for msg in messages:
            reply_id = self.send_message(
                original_message.public_key,
                msg,
                reply_content,
                original_message.id)
        self._counter.labels(type="sent-reply").inc()
        original_message.response_message = reply_content
        original_message.response_timestamp = messages[0].get("timestamp")
        original_message.reply_chat_id = reply_id
        db_session.merge(original_message)
        db_session.commit()

    def on_event(self, event_type: str, event: dict):
        with self.ctx.db.session() as db_session:
            event_data = event.get("event")
            if event_data is None:
                logger.error("Invalid event")
                return
            if event_type == EventTypeEnum.LOCAL_NOTIFICATION.value and event_data.get("category") == NotificationCategoryEnum.CONTACT_REQUEST.value:
                self.hanlde_contact_request(event_data, db_session)
                return
            if event_type == EventTypeEnum.MESSAGE.value and event_data.get("messages") is not None:
                messages = event_data.get("messages")

                if messages is None or len(messages) == 0:
                    raise ValueError("No message in the event")

                clean_msg_list = self.extract_user_messages(messages)
                if len(clean_msg_list) == 0:
                    logger.warning("No message from a user in the signal")
                    return
                if event_data.get("chats")[0].get("id") == self.group_chat.id:
                    self.find_reply(clean_msg_list, db_session)
                else:
                    self.handle_users_messages(clean_msg_list, db_session)

    def execute(self):
        if self.ctx.db is None:
            return
        logger.info("Executing module PeriodicEngagement")
        planned_messages = self.ctx.config.settings.get("periodic_messages", [])
        for planned_message in planned_messages:
            _delay = planned_message.get("delay")
            _message = planned_message.get("message")
            logger.info(f"Looking for contact to send message with delay {_delay}")
            with self.ctx.db.session() as session:
                contacts = get_all_contact_to_contact(
                    session, _delay,
                    self.ctx.config.settings.get("delay_type", "days"))
                logger.info(f"Found {len(contacts)} contacts to send a messages")
                for c in contacts:
                    self.ctx.account.send_message(chat_id=c.public_key, message=_message)
                    c.last_engagement_message = _delay
                    self._peridic_counter.labels(delay=_delay).inc()
                session.commit()

    def register_metrics(self) -> None:
        self._peridic_counter = Counter(
            "status_bot_engagement_periodic",
            "Total Message send by delay",
            ["delay"]
        )
        self._counter = Counter(
            "status_bot_engagement_actions",
            "Total Contact Request received",
            ["type"]
        )
