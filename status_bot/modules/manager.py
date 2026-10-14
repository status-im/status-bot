import importlib.util
import sys
import threading
import logging
import types
from typing import Optional, Type
from pathlib import Path

import yaml
from prometheus_client import Counter

from .base import BaseModule, ModuleConfig, ModuleContext, ModuleType
from status_bot.config import ModulesConfig
from status_bot import Database
from status_sdk import Account

logger = logging.getLogger(__name__)

# Framework files inside the modules directories that are never modules.
SKIP_MODULE_NAMES = ("base", "manager", "utils")


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` into a copy of ``base``; override wins on leaves."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_module_yaml(config_directory: Optional[str], module_name: str) -> dict:
    """Load ``<config_directory>/<module_name>.yaml`` if it exists, else ``{}``.

    Raises ``yaml.YAMLError`` on malformed YAML; a file that is not a mapping
    (or is empty) is treated as ``{}``.
    """
    if not config_directory:
        return {}
    path = Path(config_directory) / f"{module_name}.yaml"
    if not path.is_file():
        path = Path(config_directory) / f"{module_name}.yml"
        if not path.is_file():
            return {}
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    logger.info(f"Loading config file {path}")
    return data if isinstance(data, dict) else {}


class ModuleManager:
    def __init__(
        self,
        modules_config: ModulesConfig,
        account: Account,
        db: Database,
        shared_state: dict = None,
    ):
        self._modules_config = modules_config
        self._account = account
        self._db = db
        self._modules: dict[str, BaseModule] = {}
        self._module_classes: dict[str, Type[BaseModule]] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._stop_event = threading.Event()
        self._shared_state = shared_state or {}
        self._event_modules: dict[str, BaseModule] = {}
        self._max_module_retries = 3

        self._execution_error = Counter(
            "status_bot_module_execution_error", "Number of execution error per module", ["module"]
        )
        self._periodic_execution = Counter(
            "status_bot_module_execution", "Number of execution per module", ["module"]
        )
        self._module_start = Counter(
            "status_bot_module_start", "Number of Start per module", ["module"]
        )
        self._module_failure = Counter(
            "status_bot_module_start_failure", "Number of failure to start per module", ["module"]
        )

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

        config_directory = self._modules_config.config_directory
        logger.info(f"Looking at config file under {config_directory}")
        if config_directory and not Path(config_directory).is_dir():
            logger.warning(f"Module config directory not found: {config_directory}")

        logger.info(
            f"Discovered {len(self._module_classes)} module class(es): "
            f"{list(self._module_classes.keys())}"
        )

    def _discover_from_directory(self, directory: str) -> None:
        base_path = Path(directory)
        if not base_path.exists():
            logger.warning(f"Module directory not found: {directory}")
            return

        file_modules = {
            path.stem for path in base_path.glob("*.py") if not path.name.startswith("_")
        }
        dir_modules = {
            path.name
            for path in base_path.iterdir()
            if path.is_dir() and not path.name.startswith("_") and (path / "main.py").is_file()
        }

        for module_name in sorted(file_modules | dir_modules):
            if module_name in SKIP_MODULE_NAMES:
                continue

            in_file = module_name in file_modules
            in_dir = module_name in dir_modules

            if in_file and in_dir:
                logger.warning(
                    f"Module '{module_name}' exists both as a file and a directory in "
                    f"{base_path}; loading the directory version"
                )

            if in_dir:
                self._load_module(
                    module_name,
                    base_path / module_name / "main.py",
                    base_path / module_name,
                )
            else:
                self._load_module(module_name, base_path / f"{module_name}.py", None)

    def _load_module(self, module_name: str, entry_point: Path, module_dir: Optional[Path]) -> None:
        """Load a module from a single file or from ``module_dir/main.py``.

        For directory modules, ``module_dir`` is prepended to ``sys.path`` and a
        parent package is registered so sibling files can be imported both with
        plain imports (``import helpers``) and relative imports
        (``from .helpers import x``).
        """
        scan_dir = (
            entry_point.parent.resolve() if module_dir is None else module_dir.parent.resolve()
        )
        bot_modules_dir = Path(__file__).parent.resolve()
        if scan_dir == bot_modules_dir:
            pkg_name = f"status_bot.modules.{module_name}"
        else:
            pkg_name = f"bot_modules.{module_name}"

        if module_dir is not None:
            self._prepare_package_imports(pkg_name, module_dir)

        spec = importlib.util.spec_from_file_location(
            pkg_name,
            entry_point,
            submodule_search_locations=[str(module_dir)] if module_dir is not None else None,
        )
        if spec is None or spec.loader is None:
            logger.error(f"Could not create import spec for module '{module_name}' ({entry_point})")
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[pkg_name] = module
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseModule) and attr is not BaseModule:
                self._module_classes[module_name] = attr
                logger.debug(f"Found module class: {module_name}.{attr_name}")

    @staticmethod
    def _prepare_package_imports(pkg_name: str, module_dir: Path) -> None:
        """Make ``module_dir`` importable via plain and relative imports."""
        parent_name, _, _ = pkg_name.rpartition(".")
        if parent_name and parent_name not in sys.modules:
            parent = types.ModuleType(parent_name)
            parent.__path__ = []
            sys.modules[parent_name] = parent
        module_dir_str = str(module_dir)
        if module_dir_str not in sys.path:
            sys.path.insert(0, module_dir_str)

    def _resolve_module_settings(self, module_name: str) -> dict:
        """Resolve a module's settings.

        Precedence (highest first): environment variables (applied by pydantic
        before this runs) > ``<config_directory>/<module-name>.yaml`` >
        ``modules.settings.<module-name>`` in ``config.yaml``. The two YAML
        sources are deep-merged, the module YAML winning on conflicting keys.
        """
        base = self._modules_config.settings.get(module_name, {})
        if not isinstance(base, dict):
            base = {}

        try:
            yaml_settings = _load_module_yaml(self._modules_config.config_directory, module_name)
        except yaml.YAMLError as e:
            logger.error(
                f"Invalid module YAML for '{module_name}' in "
                f"'{self._modules_config.config_directory}': {e}. "
                "Falling back to config.yaml settings"
            )
            return base

        if not yaml_settings:
            return base
        logger.debug(f"Module '{module_name}' settings overlaid from module YAML")
        return _deep_merge(base, yaml_settings)

    def load_modules(self) -> None:
        enabled = set(self._modules_config.enabled)

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
            module_settings = self._resolve_module_settings(module_name)

            module_config = ModuleConfig(
                name=module_name,
                enabled=True,
                interval=module_settings.get("interval", 60),
                max_retries=self._max_module_retries,
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
        max_retries = self._max_module_retries
        backoff = module.ctx.config.backoff_seconds

        while retries <= max_retries and not self._stop_event.is_set():
            try:
                module._running = True
                self._module_start.labels(module=module.name)
                module.start()

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
                self._module_failure.labels(module=module.name).inc()
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
            try:
                module.run()
                self._periodic_execution.labels(module=module.name).inc()
            except Exception as e:
                self._execution_error.labels(module=module.name).inc()
                logger.error(f"Error when running the module {module.name}: {e}", exc_info=True)
            logger.info(f"Sleeping for {interval} min")
            self._stop_event.wait(interval)

    def _run_event_listener(self) -> None:
        for message in self._account.listen_events():
            logger.debug(f"New message {message.id}, {message.content}")
            if self._stop_event.is_set():
                break
            try:
                for module in self._event_modules.values():
                    module.run_event(message)
            except Exception as e:
                logger.error(
                    f"Error in event listener: {e}",
                    exc_info=True,
                )

    def has_alive_modules(self) -> bool:
        return any(t.is_alive() for t in self._threads.values())
