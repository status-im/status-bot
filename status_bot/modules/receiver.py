import datetime
import logging
from enum import Enum

from sqlalchemy.exc import IntegrityError

from status_bot.constants import _MESSAGE_ENCRYPTED_COLUMNS
from status_bot.models import ReceivedMessage
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.utils import derive_encryption_key, to_encrypted_value

from status_sdk.models import Message

logger = logging.getLogger(__name__)

# Column name -> ORM attribute name ("from" is stored in the `from_` attribute)
_COLUMN_TO_ATTRIBUTE = {
    attribute.expression.name: attribute.key
    for attribute in ReceivedMessage.__mapper__.column_attrs
}


def _encrypt(value, key: bytes):
    """
    Encrypt a column value, keeping `None` as `NULL`.
    """
    if value is None:
        return None
    return to_encrypted_value(str(value), key)


def _enum_value(value):
    """
    Unwrap an enum to its raw value, leave anything else untouched.
    """
    return value.value if isinstance(value, Enum) else value


def _enum_name(value):
    """
    Use the enum member name (e.g. "PRIVATE"), leave anything else as string.
    """
    if value is None:
        return None
    return value.name if isinstance(value, Enum) else str(value)


def build_message_row(message: Message, key: bytes) -> ReceivedMessage:
    """
    Convert a `status_sdk` Message into a `ReceivedMessage` row.

    Identifying and content-bearing columns (see `_MESSAGE_ENCRYPTED_COLUMNS`)
    are encrypted with AES-SIV, so the same value always maps to the same
    ciphertext and primary-key dedup keeps working. No human-readable user
    data is stored at rest.
    """
    encrypted_columns = {
        "id": message.id,
        "from": message.from_public_key,
        "response_to": message.reply_id,
        "chat_id": message.chat_id,
        "text": message.content,
    }
    content_type = _enum_value(message.content_type)
    return ReceivedMessage(
        whisper_timestamp=message.timestamp,
        content_type=int(content_type) if content_type is not None else None,
        message_type=_enum_name(message.chat_type),
        received_timestamp=datetime.datetime.now(),
        **{
            _COLUMN_TO_ATTRIBUTE[column]: _encrypt(encrypted_columns[column], key)
            for column in _MESSAGE_ENCRYPTED_COLUMNS
        },
    )


class ReceiverModule(BaseModule):
    @property
    def module_type(self) -> set[ModuleType]:
        return {ModuleType.EVENT}

    def on_start(self):
        if self.ctx.db is None:
            logger.warning("Receiver: no database configured, disabling")
            self._disabled = True
            return

        config = self.ctx.shared_state.get("config")
        secret = config.bot.encryption_key if config else ""
        self._encryption_key = derive_encryption_key(secret)
        self._disabled = False

    def execute(self):
        pass

    def on_event(self, message: Message):
        if self._disabled:
            return
        if not isinstance(message, Message):
            return

        logger.info(f"Received new message (content_type={message.content_type})")
        row = build_message_row(message, self._encryption_key)
        self._process_and_insert(row)

    def _process_and_insert(self, row: ReceivedMessage):
        with self.ctx.db.session() as session:
            try:
                session.add(row)
                session.commit()
            except IntegrityError:
                session.rollback()
                logger.warning(f"Receiver: duplicate row skipped in {row.__tablename__}")
                return
        logger.info(f"Receiver: stored 1 record in {row.__tablename__}")
