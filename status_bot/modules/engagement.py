import logging
from prometheus_client import Counter
from status_bot.constants import EventTypeEnum, NotificationCategoryEnum
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.utils import extract_contact_request
import json

logger = logging.getLogger(__name__)

class EngagementBot(BaseModule):

    DESCRIPTION = """
        Module made for Engagmement in the Status App.
        It accept all the friend request and send welcome message
    """

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.EVENT

    def on_start(self):
        logger.info("Starting module Engagement Bot")
        if self.ctx.config.settings.get("first_message") is None:
            raise ValueError("First message not missing from config")
        if self.ctx.config.settings.get("help_message") is None:
            raise ValueError("Help message not missing from config")

    def execute(self):
        pass


    def hanlde_contact_request(self, event_data: dict):
        new_contact = extract_contact_request(event_data)
        self._counter.labels(type="received_request").inc()
        logger.info(f"Accepting the contact request from {new_contact.contact_name}")
        self.ctx.account.add_contact(new_contact.public_key)
        self._counter.labels(type="accepted_request").inc()
        logger.info(f"Sending first message to {new_contact.contact_name}")
        self.ctx.account.send_message(
            chat_id=new_contact.public_key,
            message=self.ctx.config.settings.get("first_message"))
        self._counter.labels(type="first_message").inc()

    def print_help_message(self, event_data: dict):
        logger.info(json.dumps(event_data))
        message = event_data.get("messages",[])[0]
        if message is None:
            raise ValueError("No message in the event")
        dest_public_key = message.get("from")
        from_compress_key = message.get("compressedKey")
        logger.info(f"Message received from {dest_public_key} - {from_compress_key}")
        if from_compress_key == "zQ3shVf6Y3DRm4Df5F5kPhA3EGNF4F4CALj45PiNYVSFdpFx4":
            self.ctx.account.send_message(
                chat_id=dest_public_key,
                message=self.ctx.config.settings.get("help_message"),
                reply_to_message_id=message.get("id"))

    def on_event(self, event_type: str, event: dict):
        event_data = event.get("event")
        if event_data is None:
            logger.error("Invalid event")
            return
        if event_type == EventTypeEnum.LOCAL_NOTIFICATION.value and event_data.get("category") == NotificationCategoryEnum.CONTACT_REQUEST.value:
            self.hanlde_contact_request(event_data)
        if event_type == EventTypeEnum.MESSAGE.value and event_data.get("messages") != None:
            self.print_help_message(event_data)


    def register_metrics(self) -> None:
        self._counter = Counter(
            "status_bot_engagement_actions",
            "Total Contact Request received",
            ["type"]
        )
