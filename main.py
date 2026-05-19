import os
import sys
import signal
import argparse

from bot import Account, Logger
from bot.config import Config
from bot.metrics import start_prometheus
from bot.modules.manager import ModuleManager
from postgres import Postgres


def create_bot(config: Config, project_root: str) -> Account:
    account = Account(**config.bot.params.model_dump())
    available_accounts = [a["display_name"] for a in account.available_accounts]

    display_name = config.bot.display_name
    password = config.bot.password

    if display_name in available_accounts:
        account.logger.info(f"Logging in with display name: {display_name}")
        account.login(display_name=display_name, password=password)
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
        )
    else:
        raise ValueError(
            f"Account '{display_name}' not found and init_account is false. "
            f"Available accounts: {[a['display_name'] for a in available_accounts]}"
        )

    account.logger.info(f"Account Info {account.info}")

    if account.info["compressed_key"] != config.bot.compressed_key:
        raise Exception(
            "Target compressed key and logged in compressed key are different"
        )

    profile_path = os.path.join(project_root, "assets", "profile.jpg")
    account.profile_picture = profile_path
    account.logger.info(
        f"Account Information:\n"
        f"Compressed Key: {account.info['compressed_key']}\n"
        f"Public Key: {account.info['public_key']}\n"
        f"URL: {account.info['url']}"
    )
    return account


def init_postgres(config: Config) -> Postgres:
    return Postgres(
        host=config.postgres.host,
        port=config.postgres.port,
        user=config.postgres.user,
        password=config.postgres.password,
        database=config.postgres.name,
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
        account = create_bot(config, project_root)
    except Exception as e:
        logger.error(f"Failed to create bot account: {e}")
        sys.exit(1)

    db = None
    has_postgres = all([
        config.postgres.host,
        config.postgres.user,
        config.postgres.password,
        config.postgres.name,
    ])
    logger.info(f"Postgres configuration {config.postgres}")
    if has_postgres:
        try:
            db = init_postgres(config)
            logger.info("Postgres connection established")
        except Exception as e:
            logger.warning(f"Failed to connect to Postgres: {e}")
            logger.warning("Continuing without database connection")
    else:
        logger.info("No Postgres configuration found, running without database")

    manager = ModuleManager(config.modules, account, db, logger)
    manager.discover_modules()
    manager.load_modules()

    start_prometheus(config.prometheus, manager, logger)

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
