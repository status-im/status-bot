import os
import importlib.util
import threading
import logging
from typing import Optional, Type
from pathlib import Path

from .base import BaseModule, ModuleConfig, ModuleContext, ModuleType
from bot.config import ModulesConfig


class ModuleManager:

    def __init__(self, modules_config: ModulesConfig, account, db, logger: logging.Logger, shared_state: dict = None):
        self._modules_config = modules_config
        self._account = account
        self._db = db
        self._logger = logger
        self._modules: dict[str, BaseModule] = {}
        self._module_classes: dict[str, Type[BaseModule]] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._stop_event = threading.Event()
        self._shared_state = shared_state or {}

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

        self._logger.info(
            f"Discovered {len(self._module_classes)} module class(es): "
            f"{list(self._module_classes.keys())}"
        )

    def _discover_from_directory(self, directory: str) -> None:
        base_path = Path(directory)
        if not base_path.exists():
            self._logger.warning(f"Module directory not found: {directory}")
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
            pkg_name = f"bot.modules.{module_name}"
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
                self._logger.debug(f"Found module class: {module_name}.{attr_name}")

    def load_modules(self) -> None:
        enabled = set(self._modules_config.enabled)
        settings = self._modules_config.settings

        if not enabled:
            self._logger.info("No modules enabled in config")
            return

        for module_name in enabled:
            if module_name not in self._module_classes:
                self._logger.error(
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
                logger=self._logger,
                db=self._db,
                shared_state=self._shared_state,
                stop_event=self._stop_event,
            )

            try:
                module = module_class(ctx)
                self._modules[module_name] = module
                self._logger.info(f"Loaded module: {module_name}")
            except Exception as e:
                self._logger.error(f"Failed to load module '{module_name}': {e}")

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
            self._logger.info(f"Started module thread: {name}")

    def stop_all(self) -> None:
        self._logger.info("Stopping all modules...")
        self._stop_event.set()
        for name, t in self._threads.items():
            self._logger.debug(f"Waiting for module '{name}' to stop...")
            t.join(timeout=5)
            if t.is_alive():
                self._logger.warning(f"Module '{name}' did not stop in time")
        self._logger.info("All modules stopped")

    def _run_module_wrapper(self, module: BaseModule) -> None:
        retries = 0
        max_retries = module.ctx.config.max_retries
        backoff = module.ctx.config.backoff_seconds

        while retries <= max_retries and not self._stop_event.is_set():
            try:
                module._running = True
                module.on_start()

                if module.module_type == ModuleType.PERIODIC:
                    self._run_periodic(module)
                elif module.module_type == ModuleType.EVENT:
                    self._run_event(module)
                elif module.module_type == ModuleType.SERVICE:
                    module.execute()

                break

            except Exception as e:
                retries += 1
                self._logger.error(
                    f"Module '{module.name}' failed ({retries}/{max_retries}): {e}",
                    exc_info=True,
                )
                if retries <= max_retries:
                    wait = backoff * (2 ** (retries - 1))
                    self._logger.info(f"Restarting '{module.name}' in {wait}s...")
                    self._stop_event.wait(wait)
                else:
                    self._logger.error(
                        f"Module '{module.name}' permanently failed after {max_retries} retries"
                    )
            finally:
                module._running = False
                try:
                    module.on_stop()
                except Exception:
                    pass

    def _run_periodic(self, module: BaseModule) -> None:
        interval = module.ctx.config.interval
        while not self._stop_event.is_set():
            module.execute()
            self._stop_event.wait(interval)

    def _run_event(self, module: BaseModule) -> None:
        for event in self._account.signal.listen("messages.new", stop_event=self._stop_event):
            if self._stop_event.is_set():
                break
            try:
                module.on_event(event)
            except Exception as e:
                self._logger.error(
                    f"Error in event module '{module.name}': {e}",
                    exc_info=True,
                )

    def has_alive_modules(self) -> bool:
        return any(t.is_alive() for t in self._threads.values())
