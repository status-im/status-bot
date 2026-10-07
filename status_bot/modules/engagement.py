import logging
import json

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
from status_sdk.models import Message, MessageContentTypeEnum

logger = logging.getLogger(__name__)

REPLY_MSG_ERROR_IMG = "\nAn image was sent, but an error occured during the download"

IGNORED_MSG_CONTENT_TYPE = [
    15,  # Send contact request
]
MSG_TYPE_CONTACT_REQUEST = 11
MSG_TYPE_REMOVE_CONTACT = 17


def get_all_contact_to_contact(db_session: Session, delay: int, delay_unit: str):
    threshold = datetime.now() - timedelta(days=delay)
    if delay_unit != "days":
        threshold = datetime.utcnow() - timedelta(minutes=delay)
    logger.debug(f"Threshold {threshold}")

    return (
        db_session.query(ContactRequest)
        .filter(
            and_(
                ContactRequest.request_timestamp < threshold,
                ContactRequest.last_engagement_message < delay,
                ContactRequest.is_new_user,
            )
        )
        .all()
    )


def get_response_reply_if_exist(db_session: Session, message: Message) -> Optional[str]:
    if not message.reply_id:
        return None

    logger.debug(f"replying to message {message.reply_id}")
    reply_to = (
        db_session.query(FeedbackMessage)
        .filter(FeedbackMessage.reply_chat_id == message.reply_id)
        .first()
    )
    logger.debug(f"Original Message here {reply_to}")
    if reply_to:
        return reply_to.reply_chat_id

    return None


class Engagement(BaseModule):

    _mandatory_properties = [
        # Events Config
        "first_messages",
        "feedback_keywords",
        "helper_message",
        "automatic_reply",
        "group_chat",
        "new_user_message_contact_request",
        "existing_users_messages",
        "image_folder",
        # Periodic Config
        "periodic_messages",
    ]

    DESCRIPTION = """
        Module made for Engagmement in the Status App.
        It accept all the friend request and send welcome message
    """

    @property
    def module_type(self) -> set[ModuleType]:
        return {ModuleType.EVENT, ModuleType.PERIODIC}

    def on_start(self):
        logger.info("Starting module Engagement Bot")
        if self.ctx.db is None:
            raise ConnectionError("Database connection not setup")
        group_chat_config = self.settings.get("group_chat", {})
        if not group_chat_config.get("group_id"):
            logger.info("Initializing new GroupChat")
            contacts = [
                contact["public_key"]
                for contact in self.account.contacts.values()
                if contact["compressed_key"] in group_chat_config.get("participants")
            ]
            for c in contacts:
                self.account.add_contact(c)
            logger.info(f"Creating group with {contacts}")
            self.group_chat = GroupChat(self.account).create(
                public_keys=contacts, name=group_chat_config.get("name")
            )
            logger.info(f"New Group {group_chat_config.get('name')} created: {self.group_chat.id}")
        else:
            logger.info("Loading existing GroupChat")
            self.group_chat = GroupChat(
                account=self.account, chat_id=group_chat_config.get("group_id")
            )
        logger.info(f"Feedback keyword configured are: {self.settings.get('feedback_keywords')}")

    def handle_contact_request(self, message: Message, db_session: Session):
        """
        Function to handle new contact request.
        It accept all contact request, save the contact in the database
        Send the messages to the user based on `first_messages`.
        Parameters:
            - message: first message part of the event content transmitted by the Backend
            - session: ORM database session
        """
        new_contact: ContactRequest = ContactRequest(
            id=message.id,
            public_key=message.from_public_key,
            request_timestamp=message.timestamp,
            is_new_user=message.text == self.settings.get("new_user_message_contact_request", ""),
        )
        self._counter.labels(type="received_request").inc()
        self.account.add_contact(public_key=new_contact.public_key, request_id=message.id)
        db_session.merge(new_contact)
        db_session.commit()
        self._counter.labels(type="accepted_request").inc()
        message_properties = "existing_users_messages"
        if new_contact.is_new_user:
            message_properties = "first_messages"
        for msg in self.settings.get(message_properties, []):
            self.account.send_message(chat_id=new_contact.public_key, message=msg)
        self._counter.labels(type=message_properties).inc()

    def remove_contact(self, message: Message, db_session: Session):
        """
        Function to handle removal of contact.
        When a user remove the bot as a contact, all data with the user public key
        Parameters:
            - message: first message part of the event content transmitted by the Backend
            - session: ORM database session

        """
        user_public_key = message.from_public_key
        logger.info("Received a Contact Removal")
        db_session.query(FeedbackMessage).filter(
            FeedbackMessage.public_key == user_public_key
        ).delete()
        db_session.query(ContactRequest).filter(
            ContactRequest.public_key == user_public_key
        ).delete()
        db_session.commit()
        self._counter.labels(type="contact-removed").inc()

    def should_process_messages(self, message: Message) -> bool:
        """
        This function determind if the message is of the correct type and not from the bot itself.

        Parameters:
            - message: Message to process

        Output:
            - Flag to process or not
        """
        if message.compressed_key == self.account.info["compressed_key"]:
            return False
        if message.message_type in IGNORED_MSG_CONTENT_TYPE:
            return False
        return True

    def is_feedback_message(self, message: Message) -> bool:
        """
        Verify if the message concerne the feedback or is concidered spam.
        Use only the first message since multiple messages are image album
        and sahre the same text.
        """
        feedback_keywords = self.settings.get("feedback_keywords", [])
        return any(kw in message.text.lower() for kw in feedback_keywords)

    def send_message(
        self, chat_id: str, original_message: Message, reply_id: Optional[str]
    ):
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
        logger.info(f"Original received : {original_message.content_type} - {original_message.images_url}")
        send_msg_id = None
        if len(original_message.images_url) == 0:
            send_msg_id = self.account.send_message(
                chat_id=chat_id, message=original_message.text, reply_to_message_id=reply_id
            )
            return send_msg_id
        message_to_send = original_message.text
        images_path = []
        for path in original_message.images_url:
            image_id = path.split("messageId=", 1)[1]
            image_path = f"{self.settings.get('image_folder')}/{image_id}"
            logger.info(f"Path Inaital {path} - path to send {image_path}")
            try:
                logger.debug(f"Downloading image at the path {image_path}")
                download_image(
                    url=path.replace("localhost", "backend"),
                    image_path=image_path,
                )
                logger.info(f"Download image {image_path}")
                images_path.append(image_path)
            except Exception as e:
                logger.error(e)
                self._counter.labels(type="error-image-download").inc()
                message_to_send=f"{message_to_send} {REPLY_MSG_ERROR_IMG}"
        send_msg_id = self.account.send_image(
          chat_id=chat_id,
          image_paths=images_path,
          message=message_to_send,
          reply_to_message_id=reply_id,
        )
        logger.info("after send")
        return send_msg_id

    def handle_users_messages(self, message: Message, db_session: Session):
        """
        Manage messages sent to the Bot by a User
        """
        user_public_key = message.from_public_key
        reply_id = get_response_reply_if_exist(db_session, message)
        if not self.is_feedback_message(message) and not reply_id:
            logger.debug("Not matching the feedback keywords")
            self.account.send_message(
                chat_id=user_public_key,
                message=self.settings.get("helper_message"),
                reply_to_message_id=message.id,
            )
            self._counter.labels(type="invalid-feedback-query").inc()
            return

        logger.info("A new feedback message has been received")
        self.account.send_message(
            chat_id=user_public_key,
            message=self.settings.get("automatic_reply"),
            reply_to_message_id=message.id,
        )
        self._counter.labels(type="valid-feedback-query").inc()

        if not reply_id:
            # sending the config message only for the first message of a feedback
            # request, not for reply or for other photos
            self.group_chat.send_message(message=self.settings.get("group_message_text"))

        msg_id = self.send_message(self.group_chat.id, message, reply_id)

        feedback_message: FeedbackMessage = FeedbackMessage(
            id=message.id,
            public_key=user_public_key,
            request_timestamp=message.timestamp,
            group_chat_message_id=msg_id,
        )
        logger.debug(f"Sending the request {feedback_message.id} to ChatGroup")

        db_session.merge(feedback_message)
        db_session.commit()
        self._counter.labels(type="request-transfered").inc()

    """
        Manage messages sent by the GroupChat to be transfert to the users
    """

    def find_reply(self, message: Message, db_session: Session):
        if message.response_to is None:
            logger.debug("The message isn't a reply, ignoring it")
            return
        original_message: FeedbackMessage = (
            db_session.query(FeedbackMessage)
            .filter(FeedbackMessage.group_chat_message_id == message.response_to)
            .first()
        )
        if original_message is None:
            logger.warning(f"No original message found for id {message.response_to}")
            self._counter.labels(type="original-not-found").inc()
            return
        logger.debug(f"Sending reply to message {original_message.id}")
        reply_id = self.send_message(
          chat_id=original_message.public_key,
          original_message=message,
          reply_id=original_message.id
        )
        self._counter.labels(type="sent-reply").inc()
        original_message.response_message = message.text
        original_message.response_timestamp = message.timestamp
        original_message.reply_chat_id = reply_id
        db_session.merge(original_message)
        db_session.commit()

    def on_event(self, message: Message):
        with self.ctx.db.session() as db_session:
            if not self.should_process_messages(message):
                logger.warning("Message not matching the condition to be proecessed")
                return

            if message.message_type == MessageContentTypeEnum.CONTACT_REQUEST.value:
                self.handle_contact_request(message, db_session)
                return

            if message.message_type == MessageContentTypeEnum.SYSTEM_MESSAGE_MUTUAL_EVENT_REMOVED.value:
                self.remove_contact(message, db_session)
                return

            if is_group_chat_message(message, chat_id=self.group_chat.id):
                self.find_reply(message, db_session)
                return
            elif is_group_chat_message(message):
                logger.debug("Ignoring message from GroupChat outside of official group")
                return
            else:
                self.handle_users_messages(message, db_session)

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
        msgs = (
            db_session.query(FeedbackMessage)
            .filter(FeedbackMessage.request_timestamp < threshold)
            .all()
        )
        logger.info(
            f"Deleting {len(msgs)} messages having reach the retention time of {retention_time}"
        )
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
                    db_session, _delay, self.settings.get("delay_type", "days")
                )
                logger.info(
                    f"Found {len(contacts)} contacts to send the message with {_delay} delay"
                )
                for c in contacts:
                    self.account.send_message(chat_id=c.public_key, message=_message)
                    c.last_engagement_message = _delay
                    self._peridic_counter.labels(delay=_delay).inc()
                db_session.commit()

            self.delete_old_messages(db_session)
            logger.info("End of the periodic execution")

    def register_metrics(self) -> None:
        self._peridic_counter = Counter(
            "status_bot_engagement_periodic", "Total Message send by delay", ["delay"]
        )
        self._counter = Counter(
            "status_bot_engagement_actions", "Total Contact Request received", ["type"]
        )
