import logging

from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy import and_
from sqlalchemy.orm import Session

from status_bot.models import FeedbackMessage, EngagementContactRequest
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.utils import download_image, is_group_chat_message
from status_sdk.models import Message, ContactRequest

logger = logging.getLogger(__name__)


IGNORED_MSG_CONTENT_TYPE = [
    15,  # Send contact request
]
MSG_TYPE_CONTACT_REQUEST = 11
MSG_TYPE_REMOVE_CONTACT = 17


class Warning(BaseModule):
    _mandatory_properties = [
        # Events Config
        "warning_message"
    ]

    DESCRIPTION = """
        Module made to warn people of bad event.
        It accept all the friend request and send the warning message
    """

    @property
    def module_type(self) -> set[ModuleType]:
        return {ModuleType.EVENT, ModuleType.PERIODIC}

    def on_start(self):
        logger.info("Starting module Engagement Bot")
        if self.ctx.db is None:
            raise ConnectionError("Database connection not setup")

    def handle_contact_request(self, message: ContactRequest):
        """
        Function to handle new contact request.
        It accept all contact request, save the contact in the database
        Send the messages to the user based on `first_messages`.
        Parameters:
            - message: ContactRequest Send by the user
            - session: ORM database session
        """
        logger.info("New contact request received, sending warning and removing contact")
        self.account.add_contact(public_key=message.public_key, request_id=message.id)
        self.account.send_message(chat_id=message.public_key, message=self.settings.get("warning_message"))
        remove_ack = self.account.remove_contact(message.public_key)
        logger.info(f"Contact removed : {remove_ack}")



    def on_event(self, message: Message):
        if isinstance(message, ContactRequest):
            if message.incoming:
                logger.debug("A user has added the bot as a contact")
                self.handle_contact_request(message)
                return
            else:
                logger.warning("ContactRequest not handled")

        if isinstance(message, Message):
            if is_group_chat_message(message):
                logger.debug("Ignoring message from GroupChat outside of official group")
                return
            else:
                logger.info("New message received sending warning and removing contact")
                user_public_key = message.from_public_key
                self.account.send_message(
                    chat_id=user_public_key,
                    message=self.settings.get("warning_message")
                )
                remove_ack = self.account.remove_contact(user_public_key)
                logger.info(f"Contact removed : {remove_ack}")



    def execute(self):
        if self.ctx.db is None:
            return
        logger.info("Periodic executing of the module Engagement")
        for key, contact in self.account.contacts.items():
            if contact.get("mutual"):
                logger.info(f"Sending contact request to {contact.get('public_key')}")
                remove_ack = self.account.send_message(
                    chat_id=contact.get("public_key"),
                    message=self.settings.get("warning_message")
                )
                logger.info(f"Contact removed : {remove_ack}")
