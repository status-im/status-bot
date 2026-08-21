import os
import sys
import signal
import argparse
import logging

from fastapi import FastAPI

from status_sdk import Account
from status_bot import Config, Database, setup_logging
from status_bot.metrics import start_prometheus
from status_bot.modules.manager import ModuleManager

logger = logging.getLogger("status_bot.main")

def create_bot(config: Config, project_root: str) -> Account:
    account = Account(
        **config.backend.model_dump(),
        volume_folder=os.path.dirname(__file__)
    )
    account.login(
        config.bot.password,
        name=config.bot.name,
        mnemonic=config.bot.mnemonic_phrase,
        infura_token=config.bot.infura_token,
        alchemy_token=config.bot.alchemy_token,
        coingecko_api_key=config.bot.coingecko_api_key
    )

    if account.info["compressed_key"] != config.bot.chat_key:
        raise Exception(
            "Target compressed key and logged in compressed key are different."
        )

    profile_path = os.path.join(project_root, "assets", "profile.jpg")
    account.profile_picture = profile_path
    account.logger.info(
        f"\n\tAccount Information: {account.info['display_name']}\n"
        f"\tCompressed Key: {account.info['compressed_key']}\n"
        f"\tPublic Key: {account.info['public_key']}\n"
        f"\tURL: {account.info['url']}"
    )
    return account

def init_database(config: Config) -> Database:
    return Database(
        db_type=config.database.type,
        host=config.database.host,
        port=config.database.port,
        user=config.database.user,
        password=config.database.password,
        name=config.database.name
    )


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Status Bot - Modular monitoring framework"
    )
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(__file__), "config.yaml"),
        help="Path to configuration file (default: ./config.yaml)",
    )
    args = parser.parse_args()

    config_path = args.config

    try:
        logger.info("Loading the configuration")
        Config._yaml_file = config_path
        config = Config()
        setup_logging(config)
    except Exception as e:
        logger.error(f"Failed to load config: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Status Bot starting...")

    project_root = os.path.dirname(os.path.abspath(__file__))

    try:
        logger.info(
            "Configuration loaded: backend=%s database=%s modules=%s",
            config.backend.domain,
            config.database.type,
            config.modules.enabled,
        )
        account = create_bot(config, project_root)
    except Exception as e:
        logger.error(f"Failed to create bot account: {e}", exc_info=True)
        sys.exit(1)

    db = None
    has_database = all([
        config.database.host,
        config.database.user,
        config.database.password,
        config.database.name,
    ])

    if has_database:
        try:
            db = init_database(config)
            logger.info(f"Database connection established ({config.database.type})")
        except Exception as e:
            logger.warning(f"Failed to connect to database: {e}", exc_info=True)
            logger.warning("Continuing without database connection")
    else:
        logger.info("No database configuration found, running without database")

    fastapi_app = FastAPI(title="Status Bot API")
    shared_state = {"config": config, "project_root": project_root, "fastapi_app": fastapi_app}

    if config.api.enable and "api_server" not in config.modules.enabled:
        config.modules.enabled.append("api_server")

    manager = ModuleManager(config.modules, account, db, shared_state=shared_state)
    manager.discover_modules()
    manager.load_modules()

    if db is not None:
        db.create_tables(config.database.schema)

    start_prometheus(config.metrics, manager)

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
