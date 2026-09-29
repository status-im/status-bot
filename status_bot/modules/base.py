from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from status_sdk import Account
from status_bot import Database
from status_bot.exceptions import MandatoryModuleParameterMissingException
import threading
import logging
from prometheus_client import Histogram


class ModuleType(Enum):
    PERIODIC = "periodic"
    EVENT = "event"
    SERVICE = "service"


def _module_type_to_set(module_type: ModuleType) -> set[ModuleType]:
    return {module_type}


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


MODULE_PERIODIC_EXECUTION_TIME = Histogram(
    "status_bot_periodic_execution_duration_seconds", "Time spent executing jobs", ["module"]
)
MODULE_EVENT_EXECUTION_TIME = Histogram(
    "status_bot_event_execution_duration_seconds", "Time spent executing jobs", ["module"]
)


class BaseModule(ABC):

    _mandatory_properties = []

    def __init__(self, ctx: ModuleContext):
        self._ctx = ctx
        self.__logger = logging.getLogger(self.__class__.__name__)
        self._running = False
        self.__settings = ctx.config.settings
        self.__interval = ctx.config.settings.get("interval", ctx.config.interval)
        self.__db_schema = self.__settings.get("schema", self.ctx.config.name)
        self.__account = self.ctx.account

    @property
    def interval(self) -> int:
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
    def module_type(self) -> set[ModuleType]: ...

    @property
    def name(self) -> str:
        return self._ctx.config.name

    def run(self):
        with MODULE_PERIODIC_EXECUTION_TIME.labels(module=self.name).time():
            return self.execute()

    def run_event(self, event_type: str, event: dict):
        with MODULE_EVENT_EXECUTION_TIME.labels(module=self.name).time():
            return self.on_event(event_type, event)

    @abstractmethod
    def execute(self) -> Any: ...

    def start(self) -> None:
        self.logger.info(f"Starting module {self.__class__.__name__}")
        self._verify_mandatory_config()
        self.on_start()

    @abstractmethod
    def on_start(self) -> None: ...

    def on_stop(self) -> None:
        pass

    @abstractmethod
    def on_event(self, event_type: str, event: dict) -> None: ...

    def register_metrics(self) -> None:
        """Override in subclasses to register custom Prometheus metrics.

        Metrics registered here are exposed alongside the built-in bot metrics.
        This hook is only called when the Prometheus exporter is enabled
        (``metrics.enabled``); keep any metric attributes optional (``None`` by
        default) so recording code is a no-op otherwise. Labels are not added
        automatically — declare a ``module`` label with ``self.name`` when the
        metric should be attributable to a module.
        """
        pass

    def _verify_mandatory_config(self):
        missing_fields = []
        for config_field in self._mandatory_properties:
            if self.ctx.config.settings.get(config_field) is None:
                missing_fields.append(config_field)
        if len(missing_fields) > 0:
            raise MandatoryModuleParameterMissingException(
                msg="Missing fields in the config module", missing_fields=missing_fields
            )

    @property
    def is_running(self) -> bool:
        return self._running
