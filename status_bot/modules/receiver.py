import datetime
import logging

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

logger = logging.getLogger(__name__)

TIMESTAMP_DIVISOR = 1_000


def build_model_rows(
    raw_data: list[dict],
    model,
    deterministic_columns: list[str],
    drop_columns: list[str],
    pepper: str = "",
) -> list:
    timestamp_columns = {
        column.name
        for column in model.__table__.columns
        if isinstance(column.type, DateTime)
    }
    column_to_attribute = {
        attribute.expression.name: attribute.key
        for attribute in model.__mapper__.column_attrs
    }

    rows = []
    for record in raw_data:
        kwargs = {}
        for key, value in record.items():
            name = camel_to_snake(key)
            if name in drop_columns:
                continue
            if name not in column_to_attribute:
                continue
            if isinstance(value, (dict, list)):
                continue
            if value is None:
                kwargs[column_to_attribute[name]] = None
                continue
            if name in deterministic_columns:
                kwargs[column_to_attribute[name]] = to_hmac_sha256_hash(
                    str(value), pepper
                )
            elif name in timestamp_columns and isinstance(value, (int, float)):
                kwargs[column_to_attribute[name]] = datetime.datetime.fromtimestamp(
                    value / TIMESTAMP_DIVISOR
                )
            else:
                kwargs[column_to_attribute[name]] = value
        rows.append(model(**kwargs))

    return rows


class ReceiverModule(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.EVENT

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

    def on_event(self, event_type: str, event: dict):
        event_data = event.get("event", {})

        messages = event_data.get("messages", [])
        if messages:
            logger.info(f"Received {len(messages)} message(s)")
            self._process_and_insert(
                messages,
                ReceivedMessage,
                _MESSAGE_DETERMINISTIC_COLUMNS,
                _MESSAGE_DROP_COLUMNS,
            )

        chats = event_data.get("chats", [])
        if chats:
            logger.info(f"Received {len(chats)} chat(s)")
            self._process_and_insert(
                chats,
                ReceivedChat,
                _CHAT_DETERMINISTIC_COLUMNS,
                [],
            )

    def _process_and_insert(
        self,
        raw_data: list[dict],
        model,
        deterministic_columns: list[str],
        drop_columns: list[str],
    ):
        if not raw_data:
            return

        rows = build_model_rows(
            raw_data,
            model,
            deterministic_columns,
            drop_columns,
            self._pepper,
        )
        if not rows:
            return

        received_at = datetime.datetime.now()
        for row in rows:
            row.received_timestamp = received_at

        with self.ctx.db.session() as session:
            try:
                session.add_all(rows)
                session.commit()
            except IntegrityError:
                session.rollback()
                logger.warning(
                    f"Receiver: duplicate rows skipped in {model.__tablename__}"
                )
        logger.info(
            f"Receiver: stored {len(rows)} record(s) in {model.__tablename__}"
        )
