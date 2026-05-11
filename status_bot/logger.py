import json
import logging
from datetime import datetime, timezone
from typing import Optional

from status_bot.config import LoggingConfig

HUMAN_FORMAT = "%(asctime)s | %(levelname)-8s | %(threadName)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_NOISE_LOGGRS = ("sqlalchemy.engine", "urllib3", "websockets")


def _level_value(level: str) -> int:
    value = getattr(logging, level.upper(), None)
    return value if isinstance(value, int) else logging.INFO


class HumanFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(HUMAN_FORMAT, datefmt=DATE_FORMAT)


class JsonFormatter(logging.Formatter):
    def __init__(self):
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "thread": record.threadName,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class RedactFilter(logging.Filter):
    def __init__(self, secrets: list[str]):
        super().__init__()
        self._secrets = [s for s in secrets if s]

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True

        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)

        args = record.args
        if isinstance(args, dict):
            record.args = {
                k: self._redact(v) if isinstance(v, str) else v
                for k, v in args.items()
            }
        elif isinstance(args, (tuple, list)):
            record.args = type(args)(
                self._redact(a) if isinstance(a, str) else a for a in args
            )
        return True

    def _redact(self, value: str) -> str:
        for secret in self._secrets:
            if secret in value:
                value = value.replace(secret, "[REDACTED]")
        return value


def _configure_levels(config: Optional[LoggingConfig]) -> None:
    level = logging.INFO
    if config is not None:
        level = _level_value(config.level)

    logging.getLogger().setLevel(level)
    for name in _NOISE_LOGGRS:
        logging.getLogger(name).setLevel(logging.WARNING)

    access_logger = logging.getLogger("uvicorn.access")
    if config is None or config.uvicorn_access:
        access_logger.setLevel(logging.INFO)
    else:
        access_logger.setLevel(logging.WARNING)


def _collect_secrets(config) -> list[str]:
    if config is None:
        return []

    secrets = []
    bot = getattr(config, "bot", None)
    if bot is not None:
        for attr in ("password", "mnemonic_phrase", "infura_token", "coingecko_api_key", "bot_hash_pepper"):
            value = getattr(bot, attr, "")
            if value:
                secrets.append(value)

    api = getattr(config, "api", None)
    if api is not None and api.api_key:
        secrets.append(api.api_key)

    database = getattr(config, "database", None)
    if database is not None and database.password:
        secrets.append(database.password)

    return secrets


def setup_logging(config=None) -> None:
    log_config = getattr(config, "logging", config) if config is not None else None

    root = logging.getLogger()
    root.handlers.clear()

    _configure_levels(log_config)

    handler = logging.StreamHandler()
    handler.addFilter(RedactFilter(_collect_secrets(config)))

    if log_config is not None and log_config.format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    root.addHandler(handler)