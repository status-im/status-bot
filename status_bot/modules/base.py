from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from status_sdk import Account
from status_bot import Database
import threading, logging


class ModuleType(Enum):
    PERIODIC = "periodic"
    EVENT = "event"
    SERVICE = "service"


@dataclass
class ModuleConfig:
    name: str
    enabled: bool = True
    interval: int = 60
    max_retries: int = 3
    backoff_seconds: int = 30
    settings: dict = None

    def __post_init__(self):
        if self.settings is None:
            self.settings = {}


@dataclass
class ModuleContext:
    account: Account
    config: ModuleConfig
    db: Optional[Database] = None
    shared_state: dict = field(default_factory=dict)
    stop_event: Optional[threading.Event] = None


class BaseModule(ABC):

    def __init__(self, ctx: ModuleContext):
        self._ctx = ctx
        self.__logger = logging.getLogger(self.__class__.__name__)
        self._running = False
        self.__settings = ctx.config.settings
        self.__interval = ctx.config.settings.get("interval", ctx.config.interval)
        self.__db_schema = self.__settings.get("schema", self.ctx.config.name)
        self.__account = self.ctx.account

    @property
    def seconds_interval(self) -> int:
        return self.__interval

    @property
    def ctx(self) -> ModuleContext:
        return self._ctx

    @property
    def settings(self) -> dict:
        return self.__settings

    @property
    def account(self) -> Account:
        return self.__account

    @property
    def logger(self) -> logging.Logger:
        return self.__logger

    @property
    def db_schema(self) -> str:
        return self.__db_schema

    @property
    @abstractmethod
    def module_type(self) -> ModuleType:
        ...

    @property
    def name(self) -> str:
        return self._ctx.config.name

    @abstractmethod
    def execute(self) -> Any:
        ...

    def on_start(self) -> None:
        self.logger.info(f"Starting module {self.__class__.__name__}")

    def on_stop(self) -> None:
        pass

    def on_event(self, event: dict) -> Any:
        return None

    @property
    def is_running(self) -> bool:
        return self._running
