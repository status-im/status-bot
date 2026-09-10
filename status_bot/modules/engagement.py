import logging

from typing import Optional
from datetime import datetime, timedelta
from prometheus_client import Counter

from sqlalchemy import and_
from sqlalchemy.orm import Session

from status_bot.constants import EventTypeEnum
from status_bot.models import FeedbackMessage, ContactRequest
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.utils import download_image, is_group_chat_message
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
    15, # Send contact request
]
MSG_TYPE_CONTACT_REQUEST = 11
MSG_TYPE_REMOVE_CONTACT = 17


def get_all_contact_to_contact(db_session: Session, delay: int, delay_unit: str):
    threshold = datetime.now() - timedelta(days=delay)
    if delay_unit != "days":
        threshold = datetime.utcnow() - timedelta(minutes=delay)
    logger.debug(f"Threshold {threshold}")

    return db_session.query(ContactRequest).filter(
        and_(
            ContactRequest.request_timestamp < threshold,
            ContactRequest.last_engagement_message < delay,
            ContactRequest.is_new_user
        )
    ).all()

def get_response_reply_if_exist(db_session: Session, messages: list[dict]) -> Optional[str]:
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
        group_chat_config=self.settings.get("group_chat", {})
        if not group_chat_config.get("group_id"):
            logger.info("Initializing new GroupChat")
            contacts = [contact["public_key"] for contact in
                        self.account.contacts.values() if contact["compressed_key"]
                        in group_chat_config.get("participants")]
            for c in contacts:
                self.account.add_contact(c)
            logger.info(f"Creating group with {contacts}")
            self.group_chat = GroupChat(self.account).create(
                    public_keys=contacts,
                    name=group_chat_config.get("name"))
            logger.info(f"New Group {group_chat_config.get('name')} created: {self.group_chat.id}")
        else:
            logger.info("Loading existing GroupChat")
            self.group_chat = GroupChat(
                    account=self.account,
                    chat_id=group_chat_config.get("group_id"))
        logger.info(f"The bot will detect messages with the following keywords {self.settings.get('feedback_keywords', [])}")



    def handle_contact_request(self, message: dict, db_session: Session):
        """
        Function to handle new contact request.
        It accept all contact request, save the contact in the database
        Send the messages to the user based on `first_messages`.
        Parameters:
            - message: first message part of the event content transmitted by the Backend
            - session: ORM database session
        """
        new_contact: ContactRequest = ContactRequest(
            id=message.get("id"),
            public_key=message.get("from"),
            request_timestamp=datetime.fromtimestamp(
                message.get("timestamp", 0) / 1_000
            ),
            is_new_user=message.get("text") == self.settings.get("new_user_message_contact_request", ""))
        self._counter.labels(type="received_request").inc()
        self.account.add_contact(
            public_key=new_contact.public_key,
            request_id=message.get("id"))
        db_session.merge(new_contact)
        db_session.commit()
        self._counter.labels(type="accepted_request").inc()
        message_properties = "existing_users_messages"
        if new_contact.is_new_user:
            message_properties = "first_messages"
        for msg in self.settings.get(message_properties, []):
            self.account.send_message(
                chat_id=new_contact.public_key,
                message=msg)
        self._counter.labels(type=message_properties).inc()

    def remove_contact(self, message: dict, db_session: Session):
        """
        Function to handle removal of contact.
        When a user remove the bot as a contact, all data with the user public key
        Parameters:
            - message: first message part of the event content transmitted by the Backend
            - session: ORM database session

        """
        user_public_key = message.get("from")
        logger.info("Received a Contact Removal")
        db_session.query(FeedbackMessage).filter(
            FeedbackMessage.public_key == user_public_key
        ).delete()
        db_session.query(ContactRequest).filter(
            ContactRequest.public_key == user_public_key
        ).delete()
        db_session.commit()
        self._counter.labels(type="contact-removed").inc()

    def extract_user_messages(self, messages: list[dict]) -> tuple[int, list[dict]]:
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
        message_type: int = 1
        for msg in messages:
            if msg.get("compressedKey") == self.account.info["compressed_key"]:
                continue
            if msg.get("contentType") in IGNORED_MSG_CONTENT_TYPE:
                continue
            clean_msg_list.append(msg)
            message_type = msg.get("contentType", 1)

        return message_type, clean_msg_list


    def is_feedback_message(self, messages: list[dict]) -> bool:
        """
            Verify if the message concerne the feedback or is concidered spam.
            Use only the first message since multiple messages are image album
            and sahre the same text.
        """
        feedback_keywords = self.settings.get("feedback_keywords", [])
        return any(kw in messages[0].get("text").lower() for kw in feedback_keywords)

    def send_message(self, chat_id: str, orignal_message: dict, msg_content: str, reply_id: Optional[str]):
        """
            Send message to either the group chat or the user.
            Download an image with there is an image to transfer.
            Parameters:
                - chat_id: Id of the chat to contact
                - original_message: Message to transfer
                - msg_content: content of the message to tranfert
                - reply_id: optional id of the message that require a reply
            Ouput:
                - message id
        """
        send_msg_id=None
        if orignal_message.get("image"):
            image_path=f"{self.settings.get('image_folder')}/{orignal_message.get('id')}"
            try:
                logger.debug(f"Downloading image at the path {image_path}")
                download_image(
                    url=orignal_message.get("image", "").replace('localhost', 'backend'),
                    image_path=image_path)

                send_msg_id = self.account.send_image(
                        chat_id=chat_id,
                        file_path=image_path,
                        message=msg_content,
                        reply_to_message_id=reply_id)
            except Exception as e:
                logger.error(e)
                self._counter.labels(type="error-image-download").inc()
                send_msg_id = self.account.send_message(
                    chat_id=chat_id,
                    message=f"{msg_content} {REPLY_MSG_ERROR_IMG}",
                    reply_to_message_id=reply_id
                )
        else:
            send_msg_id = self.account.send_message(
                chat_id=chat_id,
                message=msg_content,
                reply_to_message_id=reply_id)

        return send_msg_id



    def handle_users_messages(self, messages: list[dict], db_session: Session):
        """
            Manage messages sent to the Bot by a User
        """
        user_public_key = messages[0].get("from")
        message_id = messages[0].get("id")
        reply_id = get_response_reply_if_exist(db_session, messages)
        if not self.is_feedback_message(messages) and not reply_id:
            logger.debug("Not matching the feedback keywords")
            self.account.send_message(
                chat_id=user_public_key,
                message=self.settings.get("helper_message"),
                reply_to_message_id=message_id)
            self._counter.labels(type="invalid-feedback-query").inc()
            return

        logger.debug("A new feedback message has been received")
        self.account.send_message(
                chat_id=user_public_key,
                message=self.settings.get("automatic_reply"),
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
                    message=self.settings.get("group_message_text"))

            msg_id = self.send_message(self.group_chat.id, msg, request_text, reply_id)

            feedback_message: FeedbackMessage = FeedbackMessage(
                id=message_id,
                public_key=user_public_key,
                request_timestamp=datetime.fromtimestamp(
                    messages[0].get("timestamp", 0) / 1_000
                ),
                group_chat_message_id=msg_id)
            logger.debug(f"Sending the request {feedback_message.id} to ChatGroup")

            db_session.merge(feedback_message)
            db_session.commit()
        self._counter.labels(type="request-transfered").inc()

    """
        Manage messages sent by the GroupChat to be transfert to the users
    """
    def find_reply(self, messages: list[dict], db_session: Session):
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
        original_message.response_timestamp = datetime.fromtimestamp(
            messages[0].get("timestamp", 0) / 1_000
        )
        original_message.reply_chat_id = reply_id
        db_session.merge(original_message)
        db_session.commit()

    def on_event(self, event_type: str, event: dict):
        with self.ctx.db.session() as db_session:
            event_data = event.get("event")
            if event_data is None:
                logger.error("Invalid event")
                return

            if event_type != EventTypeEnum.MESSAGE.value or event_data.get("messages") is None:
                return

            message_type, messages = self.extract_user_messages(event_data.get("messages", []))
            if len(messages) == 0:
                logger.warning("No message from a user in the signal")
                return

            if message_type == MSG_TYPE_CONTACT_REQUEST:
                self.handle_contact_request(messages[0], db_session)
                return

            if message_type == MSG_TYPE_REMOVE_CONTACT:
                self.remove_contact(messages[0], db_session)
                return

            if is_group_chat_message(event_data, chat_id=self.group_chat.id):
                self.find_reply(messages, db_session)
                return
            elif is_group_chat_message(event_data):
                logger.debug("Ignoring message from GroupChat outside of official group")
                return
            else:
                self.handle_users_messages(messages, db_session)


    def delete_old_messages(self, db_session: Session):
        """
        Delete all trace of messages stored for more than 31 days.
        In order to not store not necessary data.
        Parameters:
            - db_session: ORM database session
        """
        retention_time = self.settings.get("retention_time", 90)
        threshold = datetime.now() - timedelta(days=retention_time)
        # For testing purpose
        if self.settings.get("delay_type", "days") != "days":
            threshold = datetime.utcnow() - timedelta(minutes=retention_time)
        logger.debug(f"Threshold {threshold} for message deletion")
        msgs = db_session.query(FeedbackMessage).filter(
            FeedbackMessage.request_timestamp < threshold
        ).all()
        logger.info(f"Deleting {len(msgs)} messages having reach the retention time of {retention_time}")
        for msg in msgs:
            db_session.delete(msg)
            self._counter.labels(type="periodic-message-del").inc()
        db_session.commit()

    def execute(self):
        if self.ctx.db is None:
            return
        logger.info("Periodic executing of the module Engagement")
        planned_messages = self.settings.get("periodic_messages", [])
        with self.ctx.db.session() as db_session:
            for planned_message in planned_messages:
                _delay = planned_message.get("delay")
                _message = planned_message.get("message")
                contacts = get_all_contact_to_contact(
                    db_session, _delay,
                    self.settings.get("delay_type", "days"))
                logger.info(
                    f"Found {len(contacts)} contacts to send the message with {_delay} delay")
                for c in contacts:
                    self.account.send_message(chat_id=c.public_key, message=_message)
                    c.last_engagement_message = _delay
                    self._peridic_counter.labels(delay=_delay).inc()
                db_session.commit()

            self.delete_old_messages(db_session)
            logger.info("End of the periodic execution")

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
