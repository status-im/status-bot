import logging
from prometheus_client import Counter
from status_bot.constants import EventTypeEnum, NotificationCategoryEnum
from status_bot.models import SupportMessage, ContactRequest
from status_bot.models.contact_request import ContactRequest
from status_bot.models.support_message import SupportMessage
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.utils import extract_contact_request
from status_sdk import GroupChat
import json

logger = logging.getLogger(__name__)

MANDATORY_CONFIG_FIELD = ["first_messages", "support_keywords",
                          "helper_message", "automatic_reply", "group_chat"]

class EngagementEvent(BaseModule):

    DESCRIPTION = """
        Module made for Engagmement in the Status App.
        It accept all the friend request and send welcome message
    """


    @property
    def module_type(self) -> ModuleType:
        return ModuleType.EVENT

    def on_start(self):
        logger.info("Starting module Engagement Bot")
        self._verify_mandatory_config(MANDATORY_CONFIG_FIELD)
        if self.ctx.db is None:
            raise ConnectionError("Database connection not setup")
        group_chat_config=self.ctx.config.settings.get("group_chat")
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
        logger.info(f"THe bot will detect messages with the following keywords {self.ctx.config.settings.get('support_keywords', [])}")

    def execute(self):
        pass

    """
    Function to handle new Contact request from User
    """
    def hanlde_contact_request(self, event_data: dict, db_session):
        new_contact: ContactRequest = extract_contact_request(event_data)
        self._counter.labels(type="received_request").inc()
        logger.info(f"Accepting the contact request from {new_contact.public_key}")
        self.ctx.account.add_contact(new_contact.public_key)
        db_session.merge(new_contact)
        db_session.commit()
        self._counter.labels(type="accepted_request").inc()
        logger.info(f"Sending first message to {new_contact.public_key}")
        for msg in self.ctx.config.settings.get('first_messages', []):
            self.ctx.account.send_message(
                chat_id=new_contact.public_key,
                message=msg)
        self._counter.labels(type="first_messages").inc()

    """
        Verify if the message concerne the support or is concidered spam
    """
    def is_support_message(self, message) -> bool:
        support_keywords = self.ctx.config.settings.get("support_keywords", [])
        return any(kw in message.get("text").lower() for kw in support_keywords)

    """
        Manage message sent to the Bot
    """
    def handle_users_messages(self, message: dict, db_session):
        user_public_key = message.get("from")
        if not self.is_support_message(message):
            logger.info("Not matching the support keywords")
            self.ctx.account.send_message(
                chat_id=user_public_key,
                message=self.ctx.config.settings.get("helper_message"),
                reply_to_message_id=message.get("id"))
            self._counter.labels(type="invalid-support-query").inc()
            return

        logger.info(f"A new support message has been received from {user_public_key}")
        support_message: SupportMessage = SupportMessage(
            id=message.get("id"),
            public_key=message.get("from"),
            request_message=message.get("text"),
            request_timestamp=message.get("timestamp"),
            chat_id=message.get("chatId"))
        db_session.merge(support_message)
        db_session.commit()
        self.ctx.account.send_message(
                chat_id=user_public_key,
                message=self.ctx.config.settings.get("automatic_reply"),
                reply_to_message_id=message.get("id"))
        self._counter.labels(type="valid-support-query").inc()
        logger.debug(f"Sending the request {support_message.id} to ChatGroup")
        group_message_id = self.group_chat.send_message(
                message=self.ctx.config.settings.get("group_message_text"))
        group_message_id = self.group_chat.send_message(message.get("text"))
        support_message.group_support_message_id = group_message_id
        db_session.merge(support_message)
        db_session.commit()
        self._counter.labels(type="request-transfered").inc()



    """
        Manage messages sent by a support GroupChat to be transfert to the users
    """
    def find_reply(self, message: dict, db_session):
        responseTo = message.get("responseTo")
        if responseTo is None or responseTo == "":
            logger.debug("The message isn't a reply, ignoring it")
            return
        orginal_message: SupportMessage = db_session.query(SupportMessage).filter(SupportMessage.group_support_message_id==responseTo).first()
        if orginal_message == None:
            logger.warning(f"No original message found for id {responseTo}")
            self._counter.labels(type="original-not-found").inc()
            return
        # If so, check if it match a SupportMessage.group_support_message_id in db
        logger.debug(f"Sending reply to message {orginal_message.id}")
        reply_content = message.get("text")
        self.ctx.account.send_message(
                chat_id=orginal_message.public_key,
                message=reply_content,
                reply_to_message_id=orginal_message.id)
        self._counter.labels(type="sent-reply").inc()
        orginal_message.response_message = reply_content
        orginal_message.response_timestamp = message.get("timestamp")
        db_session.merge(orginal_message)
        db_session.commit()


    def on_event(self, event_type: str, event: dict):
        with self.ctx.db.session() as db_session:
            event_data = event.get("event")
            if event_data is None:
                logger.error("Invalid event")
                return
            if event_type == EventTypeEnum.LOCAL_NOTIFICATION.value and event_data.get("category") == NotificationCategoryEnum.CONTACT_REQUEST.value:
                self.hanlde_contact_request(event_data, db_session)
            if event_type == EventTypeEnum.MESSAGE.value and event_data.get("messages") != None:
                message = event_data.get("messages",[])[0]
                if message is None:
                    raise ValueError("No message in the event")
                if event_data.get("chats")[0].get("id") == self.group_chat.id:
                    self.find_reply(message, db_session)
                else:
                    self.handle_users_messages(message, db_session)


    def register_metrics(self) -> None:
        self._counter = Counter(
            "status_bot_engagement_actions",
            "Total Contact Request received",
            ["type"]
        )
