import os

import yaml
from dotenv import load_dotenv

from bot import Account
from postgres import Postgres


def load_config(file_path: str) -> dict:
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


def create_bot(config: dict, project_root: str) -> Account:
    params = config.get("bot", {}).get("params", {})
    account = Account(**params)
    available_accounts = [acc["display_name"] for acc in account.available_accounts]

    prefix = "STATUS_"
    params = {
        key.replace(prefix, "").lower(): value
        for key, value in config["env_vars"].items()
        if key.startswith(prefix)
    }
    if params["display_name"] in available_accounts:
        params.pop("mnemonic")

    account.login(**params)
    account.logger.info(f"Account Info {account.info}")
    if account.info["compressed_key"] != config["bot"]["compressed_key"]:
        raise Exception("Target compressed key and logged in compressed key are different")

    account.profile_picture = os.path.join(project_root, "assets", "profile.jpg")
    account.logger.info(
        f"Account Information:\nCompressed Key: {account.info['compressed_key']}\n"
        f"Public Key: {account.info['public_key']}\nURL: {account.info['url']}"
    )
    return account


def init_postgres(config: dict) -> Postgres:
    prefix = "POSTGRES_"
    params = {
        key.replace(prefix, "").lower(): value
        for key, value in config["env_vars"].items()
        if key.startswith(prefix)
    }
    return Postgres(**params)
