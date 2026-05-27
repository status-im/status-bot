import datetime

import pandas as pd

from bot.modules.base import BaseModule, ModuleType
from bot.modules.utils import to_sha256_hash


class ReceiverModule(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.EVENT

    def on_start(self):
        settings = self.ctx.config.settings
        self._messages_table = settings.get("messages_table", "received_messages")
        self._chats_table = settings.get("chats_table", "received_chats")
        self._hash_columns = {"id", "from", "response_to"}

        if self.ctx.db is None:
            self.ctx.logger.warning("Receiver: no database configured, disabling")
            self._disabled = True
            return

        self._disabled = False

    def execute(self):
        pass

    def on_event(self, event: dict):
        if self._disabled:
            return

        event_data = event.get("event", {})

        messages = event_data.get("messages", [])
        if messages:

            self.ctx.logger.info(f"message received {messages}")
            self._process_and_insert(messages, self._messages_table)

        chats = event_data.get("chats", [])
        if chats:
            self._process_and_insert(chats, self._chats_table)

    def _process_and_insert(self, raw_data: list[dict], table_name: str):
        if not raw_data:
            return

        df = pd.DataFrame(raw_data)
        df.columns = [col.lower() for col in df.columns]

        for col in self._hash_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).apply(to_sha256_hash)

        df["received_timestamp"] = datetime.datetime.now()

        json_columns = self._detect_json_columns(df)

        self.ctx.db.insert(df, table_name, json_columns)
        self.ctx.logger.info(
            f"Receiver: stored {len(df)} record(s) in {table_name}"
        )

    @staticmethod
    def _detect_json_columns(df: pd.DataFrame) -> list[str]:
        json_columns = []
        for col in df.columns:
            non_null = df[col].dropna()
            if len(non_null) > 0:
                first = non_null.reset_index(drop=True).iloc[0]
                if isinstance(first, (dict, list)):
                    json_columns.append(col)
        return json_columns
