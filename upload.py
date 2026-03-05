import constants, data_utils
import json, datetime, os, time, logging
import pandas as pd
from pathlib import Path, PosixPath
from postgres import Postgres
from dotenv import load_dotenv

def get_community_members(file_path: PosixPath) -> pd.DataFrame:
    """
    Get latest Status App login time for all members in the community.

    Parameters:
        - `file_path` - the `.pkl` file that has overall member information from `data_utils.get_community_info`

    Output:
        - processed data to be uploaded to the database
    """
    info: dict = pd.read_pickle(file_path)
    if not isinstance(info, dict):
        return pd.DataFrame()

    data = pd.DataFrame(info["members"]["info"]).assign(
        community_total = info["members"]["total"],
        community_id = info["community_id"],
        channels = len(info["channels"])
    )
    return data

def get_community_info(file_path: PosixPath) -> pd.DataFrame:
    """
    Get latest Status App community information

    Parameters:
        - `file_path` - the `.pkl` file that has overall member information from `data_utils.get_community_info`

    Output:
        - Single row for the given file. The data is returned in a DataFrame to make data uploading more robust
    """
    info: dict = pd.read_pickle(file_path)
    # members data can be found in function get_community_members
    if isinstance(info, dict):
        info.pop("members")
        return pd.DataFrame([info])

    return pd.DataFrame()

def get_messages(file_paths: list[str]) -> pd.DataFrame:
    """
    Convert all of the JSON messages into a DataFrame

    Parameters:
        - `file_paths` - the `Path` of `*.json` files

    Output:
        - DataFrame with all of the messages
    """
    if not file_paths:
        return pd.DataFrame()

    raw_data = []
    for file_path in file_paths:
        with open(file_path, "r") as f:
            data: dict = json.load(f)

        raw_data.append(pd.DataFrame(data["messages"]))

    data = pd.concat(raw_data, ignore_index=True)
    for column in data.columns:
        if not column.endswith("timestamp"):
            continue
        data[column] = pd.to_datetime(data[column], unit="s")

    return data.copy()

def upload(data: dict[str, pd.DataFrame], connector: Postgres, logger: logging.Logger):
    """
    Upload the raw data to Postgres.

    Parameters:
        - `data` - the raw concatenated data
        - `connector` - initialized Postgres connection
    """
    schema = constants.CONFIG["postgres"]["schema"]
    for data_key, table_name in constants.CONFIG["postgres"]["tables"].items():
        df = data[data_key]
        if len(df) == 0:
            logger.info(f"No data to upload to {schema}.{table_name}")
            continue

        df = df.assign(
            upload_timestamp = datetime.datetime.now()
        )

        json_columns = [
            column
            for column in df.columns
            if isinstance(df[column].dropna().reset_index(drop=True).iloc[0], (dict, list))
        ]
        connector.insert(df, table_name, schema, json_columns)
        logger.info(f"Uploaded {len(df)} row(s) to {schema}.{table_name}")

def run(username: str, password: str, host: str, database: str, port: str, logger: logging.Logger):

    completed = []
    path = Path(constants.UPLOAD_PATH)
    connector = Postgres(username, password, port, database, host)
    logger.info(f"Initialized Postgres connector!")
    # NOTE: the keys are the same as in config.yaml -> postgres.tables
    data = {
        "members": [],
        "community": [],
    }

    for file_path in path.rglob("*.pkl"):
        data["community"].append(get_community_info(file_path))
        data["members"].append(get_community_members(file_path))
        completed.append(file_path)
        logger.info(f"Created community and member data for {file_path}")

    for key, value in data.items():
        data[key] = pd.concat(value, ignore_index=True)

    file_paths = list(path.rglob("*.json"))
    data["messages"] = get_messages(file_paths)
    completed += file_paths

    upload(data, connector, logger)
    connector.close()

    if not completed:
        return

    for file_path in completed:
        os.remove(file_path)
        logger.info(f"Deleted {file_path}")

if __name__ == "__main__":

    logger = data_utils.get_logger("upload")
    load_dotenv()
    params = {
        "username": os.getenv("POSTGRES_USERNAME"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "host": os.getenv("POSTGRES_HOST"),
        "database": os.getenv("POSTGRES_DATABASE"),
        "port": int(os.getenv("POSTGRES_PORT")),
        "logger": logger
    }

    while True:
        run(**params)
        seconds = 60 * constants.CONFIG["sleep"]["upload"]
        logger.info(f"Sleeping for {constants.CONFIG['sleep']['upload']} minutes")
        time.sleep(seconds)
