import datetime
import logging

from pydantic_core.core_schema import invalid_schema

from sqlalchemy import DateTime
from sqlalchemy.exc import IntegrityError

from status_bot.constants import (
    _CHAT_DETERMINISTIC_COLUMNS,
    _MESSAGE_DETERMINISTIC_COLUMNS,
    _MESSAGE_DROP_COLUMNS,
)
from status_bot.models import ReceivedChat, ReceivedMessage
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.utils import camel_to_snake, to_hmac_sha256_hash

from status_sdk.models import Message

logger = logging.getLogger(__name__)

TIMESTAMP_DIVISOR = 1_000



class ReceiverModule(BaseModule):
    @property
    def module_type(self) -> set[ModuleType]:
        return {ModuleType.EVENT}

    def on_start(self):
        config = self.ctx.shared_state.get("config")
        self._pepper = config.bot.bot_hash_pepper if config else ""

        if self.ctx.db is None:
            logger.warning("Receiver: no database configured, disabling")
            self._disabled = True
            return

        self._disabled = False

    def execute(self):
        pass

    def on_event(self, message: Message):
        logger.info(f"Received new message")
        # Todo finish fixing this

    def _process_and_insert(
        self,
        message: Message,
        model,
        deterministic_columns: list[str],
        drop_columns: list[str],
    ):
        _msg = ReceivedMessage(
            id=message.id,
            whisper_timestamp = message.timestamp,
            from_ =message.from_public_key,
            text = message.content,
            chat_id = message.chat_id,
            response_to = message.reply_id,
            content_type = message.content_type,
            message_type = message.chat_type,
        )

        with self.ctx.db.session() as session:
            try:
                session.add_all(rows)
                session.commit()
            except IntegrityError:
                session.rollback()
                logger.warning(f"Receiver: duplicate rows skipped in {model.__tablename__}")
        logger.info(f"Receiver: stored {len(rows)} record(s) in {model.__tablename__}")
