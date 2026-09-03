import os
import importlib.util
import threading
import logging
from typing import Type
from pathlib import Path

from .base import BaseModule, ModuleConfig, ModuleContext, ModuleType
from status_bot.config import ModulesConfig
from status_bot.constants import EventTypeEnum
from status_bot import Database
from status_sdk import Account

logger = logging.getLogger(__name__)


class ModuleManager:

    def __init__(self, modules_config: ModulesConfig, account: Account, db: Database, shared_state: dict = None):
        self._modules_config = modules_config
        self._account = account
        self._db = db
        self._modules: dict[str, BaseModule] = {}
        self._module_classes: dict[str, Type[BaseModule]] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._stop_event = threading.Event()
        self._shared_state = shared_state or {}
        self._event_modules: dict[str, BaseModule] = {}

    @property
    def modules(self) -> dict[str, BaseModule]:
        return self._modules

    @property
    def module_names(self) -> list[str]:
        return list(self._modules.keys())

    def discover_modules(self) -> None:
        builtin_dir = str(Path(__file__).parent.resolve())
        self._discover_from_directory(builtin_dir)

        for directory in self._modules_config.directories:
            if directory == builtin_dir:
                continue
            self._discover_from_directory(directory)

        logger.info(
            f"Discovered {len(self._module_classes)} module class(es): "
            f"{list(self._module_classes.keys())}"
        )

    def _discover_from_directory(self, directory: str) -> None:
        base_path = Path(directory)
        if not base_path.exists():
            logger.warning(f"Module directory not found: {directory}")
            return

        for file_path in sorted(base_path.glob("*.py")):
            if file_path.name.startswith("_"):
                continue
            self._load_module_from_file(file_path)

    def _load_module_from_file(self, file_path: Path) -> None:
        module_name = file_path.stem

        if module_name in ("base", "manager", "utils"):
            return

        bot_modules_dir = Path(__file__).parent.resolve()
        if file_path.parent.resolve() == bot_modules_dir:
            pkg_name = f"status_bot.modules.{module_name}"
        else:
            pkg_name = f"modules.{module_name}"

        spec = importlib.util.spec_from_file_location(pkg_name, file_path)
        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseModule)
                and attr is not BaseModule
            ):
                self._module_classes[module_name] = attr
                logger.debug(f"Found module class: {module_name}.{attr_name}")

    def load_modules(self) -> None:
        enabled = set(self._modules_config.enabled)
        settings = self._modules_config.settings

        if not enabled:
            logger.info("No modules enabled in config")
            return

        for module_name in enabled:
            if module_name not in self._module_classes:
                logger.error(
                    f"Module '{module_name}' not found. "
                    f"Available: {list(self._module_classes.keys())}"
                )
                continue

            module_class = self._module_classes[module_name]
            module_settings = settings.get(module_name, {})

            module_config = ModuleConfig(
                name=module_name,
                enabled=True,
                interval=module_settings.get("interval", 60),
                max_retries=module_settings.get("max_retries", 3),
                backoff_seconds=module_settings.get("backoff_seconds", 30),
                settings=module_settings,
            )

            ctx = ModuleContext(
                account=self._account,
                config=module_config,
                db=self._db,
                shared_state=self._shared_state,
                stop_event=self._stop_event,
            )

            try:
                module = module_class(ctx)
                self._modules[module_name] = module
                if ModuleType.EVENT in module.module_type:
                    self._event_modules[module_name] = module
                logger.info(f"Loaded module: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load module '{module_name}': {e}")

    def start_all(self) -> None:
        for name, module in self._modules.items():
            t = threading.Thread(
                target=self._run_module_wrapper,
                args=(module,),
                daemon=True,
                name=f"module-{name}",
            )
            self._threads[name] = t
            t.start()
            logger.info(f"Started module thread: {name}")

        # Start centralized event listener thread
        self._event_listener_thread = threading.Thread(
            target=self._run_event_listener,
            daemon=True,
            name="event-listener",
        )
        self._event_listener_thread.start()
        logger.info("Started event listener thread")

    def stop_all(self) -> None:
        logger.info("Stopping all modules...")
        self._stop_event.set()
        for name, t in self._threads.items():
            logger.debug(f"Waiting for module '{name}' to stop...")
            t.join(timeout=5)
            if t.is_alive():
                logger.warning(f"Module '{name}' did not stop in time")
        logger.info("All modules stopped")

    def _run_module_wrapper(self, module: BaseModule) -> None:
        retries = 0
        max_retries = module.ctx.config.max_retries
        backoff = module.ctx.config.backoff_seconds

        while retries <= max_retries and not self._stop_event.is_set():
            try:
                module._running = True
                module.on_start()

                if ModuleType.SERVICE in module.module_type:
                    module.execute()
                elif ModuleType.PERIODIC in module.module_type:
                    self._run_periodic(module)
                elif ModuleType.EVENT in module.module_type:
                    # Event listening is centralized in the manager;
                    # wait until stop event is set
                    while not self._stop_event.is_set():
                        self._stop_event.wait(1)

                break

            except Exception as e:
                retries += 1
                logger.error(
                    f"Module '{module.name}' failed ({retries}/{max_retries}): {e}",
                    exc_info=True,
                )
                if retries <= max_retries:
                    wait = backoff * (2 ** (retries - 1))
                    logger.info(f"Restarting '{module.name}' in {wait}s...")
                    self._stop_event.wait(wait)
                else:
                    logger.error(
                        f"Module '{module.name}' permanently failed after {max_retries} retries"
                    )
            finally:
                module._running = False
                try:
                    module.on_stop()
                except Exception:
                    pass

    def _run_periodic(self, module: BaseModule) -> None:
        interval = module.interval * 60
        while not self._stop_event.is_set():
            module.execute()
            logger.info(f"Sleeping for {interval} min")
            self._stop_event.wait(interval)


    def _run_event_listener(self) -> None:
        for event in self._account.signal.listen([EventTypeEnum.LOCAL_NOTIFICATION.value,EventTypeEnum.MESSAGE.value]):
            event_type = event.get('type')
            logger.info(f"Received a {event_type}")
            if self._stop_event.is_set():
                break
            try:
                for module in self._event_modules.values():
                    module.on_event(event_type, event)
            except Exception as e:
                logger.error(
                    f"Error in event listener: {e}",
                    exc_info=True,
                )

    def has_alive_modules(self) -> bool:
        return any(t.is_alive() for t in self._threads.values())
