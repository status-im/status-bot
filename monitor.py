import datetime, os, pickle, yaml, time
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from multiprocessing import Process
from collections.abc import Callable
# Manual file imports
from bot import Account, Logger
from postgres import Postgres

def load_config(file_path: str) -> dict:
    """
    Load the config file and the `.env` variables

    Parameter:
        - `file_path` - the file path of the config yaml file. The `.env` variable must be in the same folder

    Output:
        - The config variables and secret from `.env`
    """
    with open(file_path, "r") as f:
        config: dict = yaml.safe_load(f)

    env_file_path = os.path.join(os.path.dirname(file_path), ".env")
    load_dotenv(env_file_path)

    config["env_vars"] = {
        key: value
        for key, value in os.environ.items()
        if key.startswith(("POSTGRES_", "STATUS_"))
    }

    return config

def download(folder: str, config: dict):
    """
    Download Status App messages / info from communities and store them in pickle files.

    Parameters:
        - `folder` - the folder where the files will be created. Sub folders are automatically created
        - `config` - the `load_config` configuration
    """
    account = Account(**config.get("bot_params", {}))
    available_accounts = [acc["display_name"] for acc in account.available_accounts]

    messages_folder = os.path.join(folder, "messages")
    os.makedirs(messages_folder, exist_ok=True)

    community_info_folder = os.path.join(folder, "community")
    os.makedirs(community_info_folder, exist_ok=True)

    members_info_folder = os.path.join(folder, "members")
    os.makedirs(members_info_folder, exist_ok=True)

    prefix = "STATUS_"
    params = {
        key.replace(prefix, "").lower(): value
        for key, value in os.environ.items()
        if key.startswith(prefix)
    }
    if params["display_name"] in available_accounts:
        params.pop("mnemonic")

    account.login(**params)

    now = datetime.datetime.now()
    # Node will only return  known / fetched messages for this channel.
    # Without enabling community archives feature the node can only fetch last 30 days (from store nodes).
    to_midnight = lambda date: date.replace(minute=0, second=0, hour=0, microsecond=0)
    start_timestamp: datetime.datetime = to_midnight(now - datetime.timedelta(days=30))
    end_timestamp: datetime.datetime = to_midnight(now - datetime.timedelta(days=1))

    get_file_name = lambda: str(datetime.datetime.now().timestamp()).replace(".", "") + ".pkl"

    for community in account.communities:
        account.logger.info(f"Extracting data for {community['name']} from {start_timestamp} to {end_timestamp}")
        community["extracted_timestamp"] = datetime.datetime.now()
        file_path = os.path.join(community_info_folder, get_file_name())
        with open(file_path, "wb") as f:
            pickle.dump(community, f)

        data = account.call_rpc("messaging", "communities")
        for result in data["result"]:
            if result["id"] != community["id"]:
                continue

            extract_timestamp = datetime.datetime.now()
            file_path = os.path.join(members_info_folder, "")
            members = pd.DataFrame([
                {
                    "community_id": community["id"],
                    "member_id": member_id,
                    "last_checked": datetime.datetime.fromtimestamp(info["last_update_clock"]) if "last_update_clock" in info else None,
                    "extract_timestamp": extract_timestamp
                }
                for member_id, info in result["members"].items()
            ])
            members.to_pickle(os.path.join(members_info_folder, get_file_name()))
            break

        for channel in community["channels"]:
            messages = account.get_messages(channel["chat_id"], start_timestamp, end_timestamp)
            file_path = os.path.join(messages_folder, get_file_name())
            messages = pd.DataFrame(messages)
            if len(messages) == 0:
                account.logger.info(f"No messages found for # {channel['name']}")
                continue

            account.logger.info(f"Extracted {len(messages)} message(s) from # {channel['name']}")
            messages.assign(
                community_id = community["id"],
                extracted_timestamp = datetime.datetime.now()
            ).to_pickle(file_path)

def upload(folder: str, config: dict):
    """
    Upload Status App `download` file to Postgres.
    NOTE: The Postgres schema must already exist

    Parameters:
        - `folder` - the folder where the files will be created. Sub folders are automatically created
        - `config` - the `load_config` configuration
    """
    path = Path(folder)
    table_name_mapping: dict[str, str] = config["postgres"]["tables"]
    table_schema = config["postgres"]["schema"]

    upload: dict[str, list] = {}
    completed = []
    for file_path in path.rglob("*.pkl"):

        table_name = table_name_mapping.get(file_path.parent.name)
        if not table_name:
            continue

        data = pd.read_pickle(file_path)
        if isinstance(data, dict):
            data = pd.DataFrame([data])

        if table_name not in upload:
            upload[table_name] = []

        upload[table_name].append(data)
        completed.append(str(file_path))

    prefix = "POSTGRES_"
    params = {
        key.replace(prefix, "").lower(): value
        for key, value in config["env_vars"].items()
        if key.startswith(prefix)
    }
    connector = Postgres(**params)
    for table_name, data in upload.items():
        if len(data) == 0:
            continue

        df = pd.concat(data, ignore_index=True)
        json_columns = [
            column
            for column in df.columns
            if isinstance(df[column].dropna().reset_index(drop=True).iloc[0], (dict, list))
        ]
        connector.insert(df, table_name, table_schema, json_columns)

    for file_path in completed:
        os.remove(file_path)

def run_factory(folder: str, config: dict, func: Callable[[str, dict], None]):
    """
    Run either `upload` or `download` function
    """
    logger = Logger()
    logger.info(f"Starting {func.__name__}")
    while True:
        func(folder, config)
        seconds = config["sleep"][func.__name__] * 60
        logger.info(f"Function {func.__name__} sleeping for {config['sleep'][func.__name__]} minute(s)")
        time.sleep(seconds)

if __name__ == "__main__":
    folder = os.path.dirname(__file__)
    config = load_config(os.path.join(folder, "config.yaml"))
    upload_folder = os.path.join(os.path.dirname(__file__), "uploads")

    download_process = Process(target=run_factory, args=(upload_folder, config, download))
    upload_process = Process(target=run_factory, args=(upload_folder, config, upload))

    upload_process.start()
    download_process.start()
