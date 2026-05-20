import os
import sys
import signal
import argparse

from fastapi import FastAPI

from bot import Account, Logger, Config, Postgres
from bot.metrics import start_prometheus
from bot.modules.manager import ModuleManager


def create_bot(config: Config, project_root: str) -> Account:
    account = Account(**config.backend.model_dump())
    available_accounts = [a["display_name"] for a in account.available_accounts]

    display_name = config.bot.display_name
    password = config.bot.password

    if display_name in available_accounts:
        account.logger.info(f"Logging in with display name: {display_name}")
        account.login(
            display_name=display_name,
            password=password,
            infura_token=config.bot.infura_token,
            coingecko_api_key=config.bot.coingecko_api_key
        )
    elif config.bot.init_account:
        mnemonic = config.bot.mnemonic_phrase
        if not mnemonic:
            raise ValueError(
                "init_account is true but no mnemonic_phrase provided"
            )
        account.logger.info(f"Creating/restoring account: {display_name}")
        account.login(
            display_name=display_name,
            password=password,
            mnemonic=mnemonic,
            infura_token=config.bot.infura_token,
            coingecko_api_key=config.bot.coingecko_api_key
        )
    else:
        raise ValueError(
            f"Account '{display_name}' not found and init_account is false. "
            f"Available accounts: {[a['display_name'] for a in available_accounts]}"
        )

    if account.info["compressed_key"] != config.bot.compressed_key:
        raise Exception(
            "Target compressed key and logged in compressed key are different."
        )

    profile_path = os.path.join(project_root, "assets", "profile.jpg")
    account.profile_picture = profile_path
    account.logger.info(
        f"Account Information: {account.info['display_name']}\n"
        f"\tCompressed Key: {account.info['compressed_key']}\n"
        f"\tPublic Key: {account.info['public_key']}\n"
        f"\tURL: {account.info['url']}"
    )
    return account


def init_postgres(config: Config) -> Postgres:
    return Postgres(
        host=config.database.host,
        port=config.database.port,
        user=config.database.user,
        password=config.database.password,
        database=config.database.name,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Status Bot - Modular monitoring framework"
    )
    parser.add_argument(
        "--config",
        default="./config.yaml",
        help="Path to configuration file (default: ./config.yaml)",
    )
    args = parser.parse_args()

    config_path = args.config

    logger = Logger()

    try:
        logger.info("Loading the configuration")
        Config._yaml_file = config_path
        config = Config()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    logger.info("Status Bot starting...")

    project_root = os.path.dirname(os.path.abspath(__file__))

    try:
        logger.info(f"{config}")
        account = create_bot(config, project_root)
    except Exception as e:
        logger.error(f"Failed to create bot account: {e}")
        sys.exit(1)

    db = None
    has_postgres = all([
        config.database.host,
        config.database.user,
        config.database.password,
        config.database.name,
    ])

    if has_postgres:
        try:
            db = init_postgres(config)
            logger.info("Postgres connection established")
        except Exception as e:
            logger.warning(f"Failed to connect to Postgres: {e}")
            logger.warning("Continuing without database connection")
    else:
        logger.info("No Postgres configuration found, running without database")

    fastapi_app = FastAPI(title="Status Bot API")
    shared_state = {"config": config, "project_root": project_root, "fastapi_app": fastapi_app}

    if config.api.enable and "api_server" not in config.modules.enabled:
        config.modules.enabled.append("api_server")

    manager = ModuleManager(config.modules, account, db, logger, shared_state=shared_state)
    manager.discover_modules()
    manager.load_modules()

    start_prometheus(config.metrics, manager, logger)

    stop_event = manager._stop_event

    def handle_sigterm(signum, frame):
        logger.info("Received SIGTERM, shutting down...")
        stop_event.set()

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    if manager.module_names:
        logger.info(
            f"Starting {len(manager.module_names)} module(s): "
            f"{manager.module_names}"
        )
        manager.start_all()

        try:
            while manager.has_alive_modules():
                stop_event.wait(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
    else:
        logger.info("No modules enabled. Bot running without modules.")
        logger.info("Press Ctrl+C to stop.")
        try:
            while True:
                stop_event.wait(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")

    manager.stop_all()
    logger.info("Status Bot stopped")


if __name__ == "__main__":
    main()
