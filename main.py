import os
import sys
import signal

from bot import Logger
from bot.config import load_config, create_bot, init_postgres
from bot.metrics import start_prometheus
from bot.modules.manager import ModuleManager


def main():
    folder = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(folder, "config.yaml")

    logger = Logger()
    try:
        logger.info("Loading the configuration")
        config = load_config(config_path)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    logger.info("Status Bot starting...")

    try:
        account = create_bot(config, folder)
    except Exception as e:
        logger.error(f"Failed to create bot account: {e}")
        sys.exit(1)

    db = None
    has_postgres = any(
        key.startswith("POSTGRES_") for key in config.get("env_vars", {})
    )
    if has_postgres:
        try:
            db = init_postgres(config)
            logger.info("Postgres connection established")
        except Exception as e:
            logger.warning(f"Failed to connect to Postgres: {e}")
            logger.warning("Continuing without database connection")
    else:
        logger.info("No Postgres configuration found, running without database")

    manager = ModuleManager(config, account, db, logger)
    manager.discover_modules()
    manager.load_modules()

    start_prometheus(config, manager, logger)

    stop_event = manager._stop_event

    def handle_sigterm(signum, frame):
        logger.info("Received SIGTERM, shutting down...")
        stop_event.set()

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    if manager.module_names:
        logger.info(f"Starting {len(manager.module_names)} module(s): {manager.module_names}")
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
