import logging

from prometheus_client import Counter

from sqlalchemy.orm import Session

from status_bot.models import FeedbackMessage, EngagementContactRequest
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.engagement.services.database import (
    delete_old_messages,
    find_original_message_if_exists,
    remove_contact,
    get_all_contact_to_contact,
    get_response_reply_if_exist,
)
from status_bot.modules.engagement.services.message import is_feedback_message, send_message

from status_bot.modules.utils import is_group_chat_message
from status_sdk import GroupChat
from status_sdk.models import Message, ContactRequest

logger = logging.getLogger(__name__)


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

    def handle_contact_request(self, message: ContactRequest, db_session: Session):
        """
        Function to handle new contact request.
        It accept all contact request, save the contact in the database
        Send the messages to the user based on `first_messages`.
        Parameters:
            - message: ContactRequest Send by the user
            - session: ORM database session
        """
        new_contact: EngagementContactRequest = EngagementContactRequest(
            id=message.id,
            public_key=message.public_key,
            request_timestamp=message.timestamp,
            is_new_user=message.text == self.settings.get("new_user_message_contact_request"),
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

    def handle_users_messages(self, message: Message, db_session: Session):
        """
        Manage messages sent to the Bot by a User
        """
        user_public_key = message.from_public_key
        reply_id = get_response_reply_if_exist(db_session, message)
        if not is_feedback_message(message, self.settings) and not reply_id:
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

        msg_id = send_message(
            self.group_chat.id, message, reply_id, self.account, self.settings, self._counter
        )

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
        original_message = find_original_message_if_exists(message, db_session, self._counter)
        if original_message is None:
            return
        logger.debug(f"Sending reply to message {original_message.id}")
        reply_id = send_message(
            chat_id=original_message.public_key,
            original_message=message,
            reply_id=original_message.id,
            account=self.account,
            settings=self.settings,
            _counter=self._counter,
        )
        self._counter.labels(type="sent-reply").inc()
        original_message.response_message = message.content
        original_message.response_timestamp = message.timestamp
        original_message.reply_chat_id = reply_id
        db_session.merge(original_message)
        db_session.commit()

    def on_event(self, message: Message):
        with self.ctx.db.session() as db_session:
            if isinstance(message, ContactRequest):
                if message.removed:
                    logger.debug("A user has removed the bot as a contact")
                    remove_contact(message, db_session, self._counter)
                    return
                if message.incoming:
                    logger.debug("A user has added the bot as a contact")
                    self.handle_contact_request(message, db_session)
                    return
                else:
                    logger.warning("ContactRequest not handled")

            if isinstance(message, Message):
                if is_group_chat_message(message, chat_id=self.group_chat.id):
                    self.find_reply(message, db_session)
                    return
                elif is_group_chat_message(message):
                    logger.debug("Ignoring message from GroupChat outside of official group")
                    return
                else:
                    self.handle_users_messages(message, db_session)

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

            delete_old_messages(db_session, self.settings, self._counter)
            logger.info("End of the periodic execution")

    def register_metrics(self) -> None:
        self._peridic_counter = Counter(
            "status_bot_engagement_periodic", "Total Message send by delay", ["delay"]
        )
        self._counter = Counter(
            "status_bot_engagement_actions", "Total Contact Request received", ["type"]
        )
