from logging import log
import os
import sys
import signal
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

from bot import Account, Logger
from bot.modules.manager import ModuleManager
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


def create_bot(config: dict) -> Account:
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

    account.profile_picture = os.path.join(os.path.dirname(__file__), "assets", "profile.jpg")
    account.logger.info(
        f"Account Information:\nCompressed Key: {account.info['compressed_key']}\n"
        f"Public Key: {account.info['public_key']}\nURL: {account.info['url']}"
    )
    return account


def init_postgres(config: dict, logger) -> Postgres:
    prefix = "POSTGRES_"
    params = {
        key.replace(prefix, "").lower(): value
        for key, value in config["env_vars"].items()
        if key.startswith(prefix)
    }
    return Postgres(**params)


def start_prometheus(config: dict, manager: ModuleManager, logger):
    prom_config = config.get("prometheus", {})
    if not prom_config.get("enabled", False):
        logger.info("Prometheus metrics disabled")
        return

    try:
        from prometheus_client import start_http_server, Gauge, Counter

        health = Gauge("status_bot_health", "Bot health status")
        version = Gauge("status_bot_version", "Bot version", ["version"])
        module_loaded = Gauge(
            "status_bot_module_loaded", "Module loaded", ["module"]
        )
        module_errors = Counter(
            "status_bot_module_errors_total", "Module errors", ["module"]
        )
        module_restarts = Counter(
            "status_bot_module_restarts_total", "Module restarts", ["module"]
        )

        health.set(1)
        version.labels(version="0.1.0").set(1)

        for module_name in manager.module_names:
            module_loaded.labels(module=module_name).set(1)

        host = prom_config.get("host", "0.0.0.0")
        port = prom_config.get("port", 8000)
        start_http_server(port, host)
        logger.info(f"Prometheus metrics server started on {host}:{port}")
    except ImportError:
        logger.warning(
            "prometheus-client not installed. Install with: pip install prometheus-client"
        )


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
        account = create_bot(config)
    except Exception as e:
        logger.error(f"Failed to create bot account: {e}")
        sys.exit(1)

    db = None
    has_postgres = any(
        key.startswith("POSTGRES_") for key in config.get("env_vars", {})
    )
    if has_postgres:
        try:
            db = init_postgres(config, logger)
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
