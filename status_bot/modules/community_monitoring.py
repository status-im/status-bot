from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules import utils
from status_bot import models
from typing import Union
from status_sdk import Community
import pandas as pd
import datetime, sqlalchemy

try:
    from detoxify import Detoxify
    import torch
except:
    pass

class CommunitiesMonitoring(BaseModule):
    """
    The module generates raw data for non-intrusive community analytics.
    Raw data can be transformed to track:
        - Daily messages sent per channel
        - Historical community members
        - Unique users
        - Overall / specific channel toxic comments

    Upcoming features:
        - Channel threads
    """

    BRIDGE_KEY = "bridge_message"
    COLUMNS = {
        "id": True,
        "whisper_timestamp": False,
        "from": True,
        "seen": False,
        "chat_id": False,
        "community_id": False,
        "message_type": False,
        "response_to": True,
        "timestamp": False,
        "deleted": False,
        "extracted_timestamp": False,
    }

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.PERIODIC

    def on_start(self):
        try:
            balance = self.account["GBP"]
            is_wallet_set = True
        except:
            is_wallet_set = False

        if not is_wallet_set:
            self.logger.warning("There was an error with loading wallet functionalities! Token gated communities will not be available! Only non token based communities will work!")

        self.__columns = {**self.COLUMNS}
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = Detoxify("original", device=device)
            self.__columns.update({
                key: False
                for key in self._model.predict("test").keys()
            })
            self.logger.info(f"Initialized Detoxify on {device}")
        except:
            self._model = None
            self.logger.info("Skipping toxic comment classification. PyPi library `detoxify` not found...")

        if not self.settings.get("detoxify", False):
            self._model = None

        if self.ctx.db is not None:
            self.ctx.db.create_tables(self.db_schema, tables=[
                models.RawMessage.__table__,
                models.RawCommunityInfo.__table__,
            ])

        super().on_start()

    def execute(self):

        community_names = self.settings.get("communities", [])
        if not community_names:
            self.logger.warning("No communities passed in config.yaml...")
            return

        now = datetime.datetime.now()
        latest_dates = self.get_latest_dates()
        batch: dict[str, list[Union[dict, pd.DataFrame]]] = {
            "messages": [],
            "community": []
        }
        for info in self.account.communities:
            community = Community(self.account, info["id"])
            if community.name not in community_names:
                continue

            batch["community"].append(
                models.RawCommunityInfo(**info, batch_timestamp = datetime.datetime.now())
            )
            messages = self.get_messages(community, now, latest_dates)
            self.logger.info(f"Community '{community.name}' has {len(messages)} message(s)")
            if len(messages) == 0:
                continue

            batch["messages"].append(messages)

        if batch["messages"]:
            batch["messages"] = pd.concat(batch["messages"])

        for batch_type, data in batch.items():

            if len(data) == 0:
                continue

            if batch_type != "messages":
                with self.ctx.db.session(self.db_schema) as session:
                    session.add_all(data)
                    session.commit()
                continue

            records = data.assign(batch_timestamp=datetime.datetime.now())\
                            .to_dict("records")

            with self.ctx.db.session(self.db_schema) as session:
                session.execute(sqlalchemy.insert(models.RawMessage.__table__), records)
                session.commit()

    def get_latest_dates(self) -> dict[str, pd.Timestamp]:
        """
        Get the latest date for every channel
        """
        if self.ctx.db is None:
            return {}

        query = sqlalchemy.select(
            models.RawMessage.chat_id,
            sqlalchemy.func.max(models.RawMessage.whisper_timestamp),
        ).group_by(models.RawMessage.chat_id)

        try:
            with self.ctx.db.session(self.db_schema) as session:
                return {
                    chat_id: pd.Timestamp(latest)
                    for chat_id, latest in session.execute(query)
                }
        except Exception as e:
            self.logger.exception(f"Could not read history from {self.db_schema}... {e}")
            return {}



    def get_messages(self, community: Community, now: datetime.datetime, latest_dates: dict[str, pd.Timestamp]) -> pd.DataFrame:
        data = []
        # (1) Get raw messages
        for channel_info in community.channels:
            channel = community[channel_info["name"]]
            start_timestamp = latest_dates.get(channel.id)
            if start_timestamp:
                start_timestamp += datetime.timedelta(seconds=1)
            else:
                start_timestamp = utils.to_midnight(now - datetime.timedelta(days=30))

            messages = channel.get_messages(start_timestamp, now)
            messages = pd.DataFrame(messages)
            if len(messages) == 0:
                continue

            messages = messages.assign(
                community_id=community.id,
                extracted_timestamp=now,
            )
            data.append(messages)

        final = pd.concat(data, ignore_index=True) if data else pd.DataFrame()
        if len(final) == 0:
            return pd.DataFrame()

        # (2) Add additional metrics
        if self._model:
            final = final.merge(
                final["text"].apply(lambda text: pd.Series(self._model.predict(utils.remove_public_key(text)))),
                "left",
                left_index=True,
                right_index=True
            )

        # (3) Prepare for database upload
        existing_columns = final.columns.to_list()
        for column, should_hash in self.__columns.items():
            if column not in existing_columns:
                loc = len(final.columns.to_list())
                final.insert(loc, column, None)
                continue

            if should_hash:
                final[column] = final[column].astype(str).apply(utils.to_sha256_hash)

        if self.BRIDGE_KEY in existing_columns:
            final["source"] = final[self.BRIDGE_KEY].apply(
                lambda value: value.get("bridgeName", "status") if not pd.isna(value) else "status"
            )
        else:
            final["source"] = "status"

        final = final[list(self.__columns.keys()) + ["source"]].assign(
            deleted = final["deleted"].fillna(False),
            seen = final["seen"].fillna(False),
        )

        return final.copy()
