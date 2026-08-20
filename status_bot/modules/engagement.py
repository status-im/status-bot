import logging
from prometheus_client import Counter, Gauge
from status_bot.constants import EventTypeEnum, NotificationCategoryEnum
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.utils import extract_contact_request

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
            raise ValueError("First Message not missing from config")
        pass
    def execute(self):
        pass

    def on_event(self, event_type: str, event: dict):
        event_data = event.get("event")
        if event_data is None or event_type != EventTypeEnum.LOCAL_NOTIFICATION.value or event_data.get("category") != NotificationCategoryEnum.CONTACT_REQUEST.value:
            logger.debug("Not a friend request")
            return
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


    def register_metrics(self) -> None:
        self._counter = Counter(
            "status_bot_engagement_actions",
            "Total Contact Request received",
            ["type"]
        )
