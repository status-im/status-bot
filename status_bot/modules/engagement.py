import logging
from status_bot.constants import EventTypeEnum, NotificationCategoryEnum
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.utils import extract_contact_request

logger = logging.getLogger(__name__)


class NewContact():

    def __init__(self, public_key:str, name: str):
        self.public_key = public_key
        self.name = name

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
        if event_data is None:
            logger.info("reject")
            return
        logging.info(f"Received {event_type} - {EventTypeEnum.LOCAL_NOTIFICATION.value}")
        if event_type != EventTypeEnum.LOCAL_NOTIFICATION.value:
            logger.info("Not Correcty Type")
            return
        logger.info(f"Received {event_data.get('category')}")
        if event_data.get("category") != NotificationCategoryEnum.CONTACT_REQUEST.value:
            logger.info("rejected category")
            return
        new_contact = extract_contact_request(event_data)
        logger.info(f"Accepting the contact request from {new_contact.contact_name}")
        self.ctx.account.add_contact(new_contact.public_key)
        logger.info(f"Sending first message to {new_contact.contact_name}")
        self.ctx.account.send_message(
            chat_id=new_contact.public_key,
            message=self.ctx.config.settings.get("first_message"))
