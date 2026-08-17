import datetime, os, logging
from pathlib import Path

import pandas as pd
from status_sdk import Account, Community
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.utils import save_file, to_midnight, to_sha256_hash, remove_public_key
from status_bot import Config
from typing import Optional

try:
    from detoxify import Detoxify
    import torch
except:
    pass

def extract_community_channels(account: Account, community: Community, latest_dates: dict[str, pd.Timestamp], model: Optional[Detoxify] = None) -> pd.DataFrame:
    bridge_key = "bridge_message"
    logger = account.logger
    columns = {
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

    if model:
        columns.update({
            key: False
            for key in model.predict("test").keys()
        })

    final = []
    for channel_info in community.channels:
        now = datetime.datetime.now()
        channel = community[channel_info["name"]]

        start_timestamp = latest_dates.get(channel.id)
        if start_timestamp:
            start_timestamp += datetime.timedelta(seconds=1)
        else:
            start_timestamp = to_midnight(now - datetime.timedelta(days=30))

        account.logger.info(f"Starting message extraction for # {channel.name} [{start_timestamp} - {now}]")
        messages = channel.get_messages(start_timestamp, now)
        messages = pd.DataFrame(messages)
        if len(messages) == 0:
            logger.info("No messages found")
            continue

        logger.info(f"Extracted {len(messages)} message(s)")
        messages = messages.assign(
            community_id=community.id,
            extracted_timestamp=now,
        )
        final.append(messages)

    extracted_data = pd.concat(final, ignore_index=True) if final else pd.DataFrame()
    if len(extracted_data) == 0:
        return extracted_data

    if model:
        extracted_data = extracted_data.merge(
            extracted_data["text"].apply(lambda text: pd.Series(model.predict(remove_public_key(text)))),
            "left",
            left_index=True,
            right_index=True
        )

    existing_columns = extracted_data.columns.to_list()
    for column, should_hash in columns.items():
        if column not in existing_columns:
            loc = len(extracted_data.columns.to_list())
            extracted_data.insert(loc, column, None)
            continue

        if should_hash:
            extracted_data[column] = extracted_data[column].astype(str).apply(to_sha256_hash)

    if bridge_key in extracted_data.columns:
        extracted_data["source"] = extracted_data[bridge_key].apply(
            lambda value: value.get("bridgeName", "status") if not pd.isna(value) else "status"
        )
    else:
        extracted_data["source"] = "status"

    extracted_data = extracted_data[list(columns.keys()) + ["source"]].assign(
        deleted=extracted_data["deleted"].fillna(False),
        seen=extracted_data["seen"].fillna(False),
    )
    logger.info("Sensitive data has been hashed")

    return extracted_data


class MonitoringModule(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.PERIODIC

    def on_start(self) -> None:
        account = self.context.account
        logger = account.logger

        balance = account["GBP"]
        query = (
            (balance["symbol"] == "SNT")
            & (balance["fiat_value"] > 0)
            & (balance["chain_id"] == 1)
        )
        if query.sum() != 1:
            raise RuntimeError("Wallet balance check failed — Infura or Coingecko issue")

        logger.info(self.context.config.settings)

        settings = self.context.config.settings
        if not settings.get("detoxify", False):
            self._model = None
            return

        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = Detoxify("original", device=device)
            logger.info(f"Initialized Detoxify on {device}")
        except:
            self._model = None
            logger.info("Skipping toxic comment classification. PyPi library `detoxify` not found...")


    def execute(self):
        config: Config = self.context.shared_state.get("config")
        if config is None:
            self.context.logger.error("MonitoringModule: config not found in shared_state")
            return

        project_root = self.context.shared_state.get("project_root")
        if not project_root:
            project_root = os.path.dirname(os.path.abspath(__file__))

        account = self.context.account
        logger = account.logger

        upload_folder = self.context.config.settings.get("upload_folder", "uploads")
        upload_path = os.path.join(project_root, upload_folder)
        current_state_path = os.path.join(project_root, config.files.current_state)

        self._download(account, upload_path, current_state_path)

        if self.context.db is not None:
            self._store(upload_path, current_state_path, config, logger)
        else:
            logger.info("No database configured, skipping store step")

    def _download(self, account: Account, upload_path: str, current_state_path: str):
        latest_dates: dict[str, pd.Timestamp] = (
            pd.read_pickle(current_state_path) if os.path.exists(current_state_path) else {}
        )
        logger = account.logger
        get_file_name = lambda: str(to_midnight(datetime.datetime.now()).timestamp()).replace(".", "")
        communities = account.communities
        if not communities:
            logger.warning("No communities found...")
            return

        for community_info in communities:

            community = Community(account, community_info["id"])
            if not community.is_member:
                continue

            community_name = community.name
            community_folder_name = community_name.replace(" ", "-")
            messages_folder = os.path.join(upload_path, "messages", community_folder_name)
            community_info_folder = os.path.join(upload_path, "community", community_folder_name)

            account.logger.info(f"Extracting data for {community_name}")

            file_path = os.path.join(community_info_folder, get_file_name() + ".pkl")
            if not os.path.exists(file_path):
                save_file(file_path, community_info)
                account.logger.info(f"Created {file_path}")

            file_path = os.path.join(messages_folder, get_file_name() + ".csv")
            if not os.path.exists(file_path):
                messages = extract_community_channels(account, community, latest_dates, self._model)
                if len(messages) > 0:
                    save_file(file_path, messages)
                    logger.info(f"Created {file_path}")

    def _store(self, upload_path: str, current_state_path: str, config: Config, logger: logging.Logger):
        path = Path(upload_path)
        table_name_mapping: dict[str, str] = config.modules.settings.get("monitoring", {}).get("tables", {})
        upload: dict[str, list] = {}
        latest_dates: dict[str, pd.Timestamp] = (
            pd.read_pickle(current_state_path) if os.path.exists(current_state_path) else {}
        )
        completed = []

        files = list(path.rglob("*.pkl")) + list(path.rglob("*.csv"))
        logger.info(f"There are {len(files)} file(s) to upload")
        for file_path in files:
            table_name = table_name_mapping.get(file_path.parent.parent.name)
            if not table_name:
                continue

            file_name = str(file_path.name)
            data = pd.read_pickle(file_path) if file_name.endswith(".pkl") else pd.read_csv(file_path)
            if isinstance(data, dict):
                data = pd.DataFrame([data])

            for column in data.columns:
                if "timestamp" not in column:
                    continue
                data[column] = pd.to_datetime(data[column])

            if table_name not in upload:
                upload[table_name] = []

            if "timestamp" in data.columns:
                latest_dates.update(data.groupby("chat_id")["timestamp"].max().to_dict())

            upload[table_name].append(data)
            completed.append(str(file_path))

        save_file(current_state_path, latest_dates)
        logger.info(f"Updated {current_state_path}")

        connector = self.context.db
        for table_name, data in upload.items():
            if len(data) == 0:
                continue

            df = pd.concat(data, ignore_index=True).assign(batch_timestamp=datetime.datetime.now())
            json_columns = [
                column
                for column in df.columns
                if len(df[column].dropna()) > 0
                and isinstance(df[column].dropna().reset_index(drop=True).iloc[0], (dict, list))
            ]
            connector.insert(df, table_name, json_columns)
            logger.info(f"Uploaded {len(df)} record(s) to {table_name}")

        for file_path in completed:
            os.remove(file_path)
            logger.info(f"Deleted {file_path}")
