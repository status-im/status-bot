import datetime
import logging

import pandas as pd

from status_bot import Config
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.utils import camel_to_snake, generate_salt, to_hmac_sha256_hash
from status_bot.constants import _MESSAGE_DETERMINISTIC_COLUMNS, _MESSAGE_DROP_COLUMNS,_MESSAGE_SALTED_COLUMNS, _CHAT_SALTED_COLUMNS, _CHAT_DETERMINISTIC_COLUMNS, _SALT_COLUMN

logger = logging.getLogger(__name__)


def transform_dataframe(
    df: pd.DataFrame,
    deterministic_columns: list[str],
    salted_columns: list[str],
    drop_columns: list[str],
    pepper: str = "",
) -> pd.DataFrame:
    df = df.copy()
    df.columns = [camel_to_snake(col) for col in df.columns]

    for col in drop_columns:
        if col in df.columns:
            df = df.drop(columns=[col])

    for col in deterministic_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).apply(
                lambda value: to_hmac_sha256_hash(value, pepper)
            )

    salted_cols = [col for col in salted_columns if col in df.columns]
    if salted_cols:
        salts = [generate_salt() for _ in range(len(df))]
        for col in salted_cols:
            df[col] = [
                to_hmac_sha256_hash(str(value), pepper, salts[i])
                for i, value in enumerate(df[col].values)
            ]
        df[_SALT_COLUMN] = salts

    for col in df.columns:
        non_null = df[col].dropna()
        if len(non_null) > 0:
            first = non_null.reset_index(drop=True).iloc[0]
            if isinstance(first, (dict, list)):
                logger.warning(
                    f"Receiver: dropping unexpected column {col} "
                    f"containing structured data"
                )
                df = df.drop(columns=[col])

    return df


class ReceiverModule(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.EVENT

    def on_start(self):
        settings = self.context.config.settings
        self._messages_table = settings.get("messages_table", "received_messages")
        self._chats_table = settings.get("chats_table", "received_chats")

        config: Config = self.context.shared_state.get("config")
        self._pepper = config.bot.bot_hash_pepper if config else ""

        if self.context.db is None:
            self.context.logger.warning("Receiver: no database configured, disabling")
            self._disabled = True
            return

        self._disabled = False

    def execute(self):
        pass

    def on_event(self, event: dict):
        if self._disabled:
            return

        event_data = event.get("event", {})

        messages: list[dict] = event_data.get("messages", [])
        if messages:
            logger.info(f"Received {len(messages)} message(s)")
            self._process_and_insert(
                messages,
                self._messages_table,
                _MESSAGE_DETERMINISTIC_COLUMNS,
                _MESSAGE_SALTED_COLUMNS,
                _MESSAGE_DROP_COLUMNS,
            )

        chats = event_data.get("chats", [])
        if chats:
            self._process_and_insert(
                chats,
                self._chats_table,
                _CHAT_DETERMINISTIC_COLUMNS,
                _CHAT_SALTED_COLUMNS,
                [],
            )

    def _process_and_insert(
        self,
        raw_data: list[dict],
        table_name: str,
        deterministic_columns: list[str],
        salted_columns: list[str],
        drop_columns: list[str],
    ):
        if not raw_data:
            return

        df = pd.DataFrame(raw_data)
        df = transform_dataframe(
            df,
            deterministic_columns,
            salted_columns,
            drop_columns,
            self._pepper,
        )

        df["received_timestamp"] = datetime.datetime.now()

        self.context.db.insert(df, table_name, [])
        self.context.logger.info(f"Receiver: stored {len(df)} record(s) in {table_name}")
