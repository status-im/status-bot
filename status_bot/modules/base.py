from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from status_sdk import Account
import threading
import logging

if TYPE_CHECKING:
    from status_bot import Database


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
    logger: logging.Logger
    db: Optional[Database] = None
    shared_state: dict = field(default_factory=dict)
    stop_event: Optional[threading.Event] = None


class BaseModule(ABC):

    def __init__(self, context: ModuleContext):
        self._context = context
        self._running = False

    @property
    def context(self) -> ModuleContext:
        return self._context

    @property
    @abstractmethod
    def module_type(self) -> ModuleType:
        ...

    @property
    def name(self) -> str:
        return self._context.config.name

    @abstractmethod
    def execute(self) -> Any:
        ...

    def on_start(self) -> None:
        pass

    def on_stop(self) -> None:
        pass

    def on_event(self, event: dict) -> Any:
        return None

    @property
    def is_running(self) -> bool:
        return self._running
