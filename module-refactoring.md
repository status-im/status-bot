# Refactoring Plan: Status Bot Modular Architecture

## Overview

Transform `monitor.py` from a monolithic script into a modular plugin-based system where modules are independent, configurable, and can run in periodic or event-driven mode.

## Architecture Design

```
┌─────────────────────────────────────────────────────────────┐
│                        Main Bot                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   Config     │  │    Account   │  │  Module Manager  │   │
│  │   Loader     │  │   (shared)   │  │  (loads/runs)    │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                  │                    │
         ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                     Modules (plugins)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐        │
│  │ Monitoring  │  │  Storage    │  │   Custom      │  ...   │
│  │  (periodic) │  │  (periodic) │  │(event-driven) │        │
│  └─────────────┘  └─────────────┘  └───────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Base Module Interface (`bot/modules/base.py`)

- Abstract base class defining module contract
- Required methods: `run()`, `get_name()`, `get_config()`
- Optional: `on_start()`, `on_stop()`, `on_event()`

### 2. Module Manager (`bot/modules/manager.py`)

- Discovers modules from configured directory
- Loads/enables/disables based on config
- Handles lifecycle (init → start → run → stop)
- Isolates errors per module

### 3. Configuration (`config.yaml`)

```yaml
modules:
  enabled:
    - monitoring
    - storage
  directories:
    - ./modules
  settings:
    monitoring:
      interval: 600  # seconds
    storage:
      batch_size: 100
```

### 4. Module Structure (`modules/`)

- Each module is a Python file with a Module class
- Auto-discovery via naming convention or decorator

## Module Types Support

| Module Type | Execution | Example |
|-------------|-----------|---------|
| `periodic` | Runs on interval | Monitoring, Storage |
| `event` | Reacts to signals | Mentions, Analytics |
| `service` | Long-running | WebSocket listeners |

## Implementation Steps

### Phase 1: Core Framework

#### 1. Directory Structure

```
bot/
├── __init__.py
├── account.py
├── signal.py
├── logger.py
└── modules/
    ├── __init__.py
    ├── base.py          # BaseModule abstract class
    └── manager.py       # ModuleManager class
modules/                 # Custom modules directory (user-created)
    ├── __init__.py
    └── example.py
```

#### 2. BaseModule Abstract Class (`bot/modules/base.py`)

```python
from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging


class ModuleType(Enum):
    """Defines how the module is executed."""
    PERIODIC = "periodic"      # Runs on a fixed interval
    EVENT = "event"           # Reacts to signals/events
    SERVICE = "service"       # Long-running service


@dataclass
class ModuleConfig:
    """Configuration for a single module."""
    name: str
    enabled: bool = True
    interval: int = 60        # seconds, for periodic modules
    settings: dict = None    # module-specific settings

    def __post_init__(self):
        if self.settings is None:
            self.settings = {}


class BaseModule(ABC):
    """
    Abstract base class for all bot modules.

    Subclass this to create custom modules. Implement the required methods.
    """

    def __init__(
        self,
        config: ModuleConfig,
        account: "Account",
        logger: logging.Logger
    ):
        """
        Initialize the module.

        Args:
            config: Module configuration from config.yaml
            account: Shared Status account instance
            logger: Shared logger instance
        """
        self._config = config
        self._account = account
        self._logger = logger
        self._running = False

    @property
    def name(self) -> str:
        """Module name, used for identification."""
        return self._config.name

    @property
    def module_type(self) -> ModuleType:
        """Return the type of module. Override in subclass."""
        return ModuleType.PERIODIC

    @property
    def interval(self) -> int:
        """Interval in seconds for periodic modules."""
        return self._config.interval

    @abstractmethod
    def run(self) -> Any:
        """
        Execute the module logic.

        This is called either:
        - Periodically (for PERIODIC type)
        - On event (for EVENT type)
        - Once and keeps running (for SERVICE type)

        Returns:
            Any result from the module execution
        """
        pass

    def on_start(self) -> None:
        """
        Called once when the module starts.
        Override for initialization logic.
        """
        pass

    def on_stop(self) -> None:
        """
        Called once when the module stops.
        Override for cleanup logic.
        """
        pass

    def on_event(self, event: dict) -> Any:
        """
        Handle an event signal (for EVENT type modules).

        Override to handle specific signals like 'messages.new'.

        Args:
            event: The event data from Signal

        Returns:
            Any result from handling the event
        """
        return None

    def is_running(self) -> bool:
        """Check if module is currently running."""
        return self._running

    def _set_running(self, value: bool) -> None:
        """Internal: update running state."""
        self._running = value
```

#### 3. Module Manager (`bot/modules/manager.py`)

```python
import os
import importlib.util
import logging
from typing import Type, Optional, List, Dict, Any
from pathlib import Path

from .base import BaseModule, ModuleConfig, ModuleType
from bot import Account


class ModuleManager:
    """
    Manages module discovery, loading, and lifecycle.

    Handles:
    - Discovering modules from configured directories
    - Loading and initializing modules
    - Running modules according to their type
    - Error isolation between modules
    """

    def __init__(
        self,
        config: dict,
        account: Account,
        logger: logging.Logger
    ):
        """
        Initialize the module manager.

        Args:
            config: The full bot configuration dict
            account: Shared Account instance
            logger: Shared logger instance
        """
        self._config = config
        self._account = account
        self._logger = logger
        self._modules: Dict[str, BaseModule] = {}
        self._module_classes: Dict[str, Type[BaseModule]] = {}

    @property
    def modules(self) -> Dict[str, BaseModule]:
        """Get all loaded modules."""
        return self._modules

    def discover_modules(self) -> None:
        """Discover available module classes from configured directories."""
        modules_config = self._config.get("modules", {})
        directories = modules_config.get("directories", ["modules"])
        enabled = modules_config.get("enabled", [])

        for directory in directories:
            self._discover_from_directory(directory)

        self._logger.info(
            f"Discovered {len(self._module_classes)} module classes: "
            f"{list(self._module_classes.keys())}"
        )

    def _discover_from_directory(self, directory: str) -> None:
        """Discover modules from a specific directory."""
        base_path = Path(directory)
        if not base_path.exists():
            self._logger.warning(f"Module directory not found: {directory}")
            return

        for file_path in base_path.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            self._load_module_from_file(file_path)

    def _load_module_from_file(self, file_path: Path) -> None:
        """Load a module class from a Python file."""
        module_name = file_path.stem

        spec = importlib.util.spec_from_file_location(
            f"modules.{module_name}", file_path
        )
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
        """Load and initialize all enabled modules."""
        modules_config = self._config.get("modules", {})
        enabled = set(modules_config.get("enabled", []))
        settings = modules_config.get("settings", {})

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
                settings=module_settings
            )

            try:
                module = module_class(module_config, self._account, self._logger)
                self._modules[module_name] = module
                self._logger.info(f"Loaded module: {module_name}")
            except Exception as e:
                self._logger.error(f"Failed to load module '{module_name}': {e}")

    def start_modules(self) -> None:
        """Call on_start for all modules."""
        for module in self._modules.values():
            try:
                module.on_start()
            except Exception as e:
                self._logger.error(
                    f"Error starting module '{module.name}': {e}"
                )

    def run_modules(self) -> None:
        """
        Run all modules according to their type.

        - PERIODIC: runs in a loop with configured interval
        - EVENT: registers with signal listener
        - SERVICE: runs once and keeps running
        """
        for module in self._modules.values():
            try:
                if module.module_type == ModuleType.PERIODIC:
                    self._run_periodic_module(module)
                elif module.module_type == ModuleType.EVENT:
                    self._run_event_module(module)
                elif module.module_type == ModuleType.SERVICE:
                    self._run_service_module(module)
            except Exception as e:
                self._logger.error(
                    f"Error running module '{module.name}': {e}"
                )

    def _run_periodic_module(self, module: BaseModule) -> None:
        """Run a periodic module on its interval."""
        import time
        while True:
            try:
                module.run()
            except Exception as e:
                self._logger.error(
                    f"Error in periodic module '{module.name}': {e}"
                )
            time.sleep(module.interval)

    def _run_event_module(self, module: BaseModule) -> None:
        """Run an event-driven module by listening to signals."""
        for event in self._account.signal.listen("messages.new"):
            try:
                module.on_event(event)
            except Exception as e:
                self._logger.error(
                    f"Error handling event in module '{module.name}': {e}"
                )

    def _run_service_module(self, module: BaseModule) -> None:
        """Run a service module once (blocking)."""
        module.run()

    def stop_modules(self) -> None:
        """Call on_stop for all modules."""
        for module in self._modules.values():
            try:
                module.on_stop()
            except Exception as e:
                self._logger.error(
                    f"Error stopping module '{module.name}': {e}"
                )
```

#### 4. Configuration Example (`config.yaml`)

```yaml
postgres:
  schema: "status_app_monitoring"
  tables:
    messages: "raw_messages"
    community: "raw_community_info"

sleep: 10

files:
  current_state: "dates.pkl"

bot:
  public_key: "0x041658626a9e1303b631f6d0fb1e047211d5603b977454f7d5d29fe583c3d6c1bd3d8e395d67f6c44b5bc659aae912040e9dd8164b5107368a29029cb53389d8b0"
  compressed_key: "zQ3shNv1tnajHo5FvCvP662cWcbBfS5ZejB4TWaH9iAuFCZZe"
  params:
    domain: "status-backend"
    port: 8080
    is_secure: false

modules:
  directories:
    - ./modules
  enabled:
    - monitoring
    - storage
  settings:
    monitoring:
      interval: 600
    storage:
      batch_size: 100
```

#### 5. Example Custom Module (`modules/example.py`)

```python
from bot.modules.base import BaseModule, ModuleConfig, ModuleType
from typing import Any


class ExampleModule(BaseModule):
    """
    Example module that demonstrates the module interface.

    This module logs a message every interval seconds.
    """

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.PERIODIC

    def run(self) -> Any:
        """Run the module logic."""
        self._logger.info(f"Example module running for {self._account.info['display_name']}")
        # Custom logic here:
        # - Process messages
        # - Send notifications
        # - Store data
        # - etc.

    def on_start(self) -> None:
        """Called when module starts."""
        self._logger.info(f"Starting example module with interval {self.interval}s")

    def on_stop(self) -> None:
        """Called when module stops."""
        self._logger.info("Stopping example module")
```

#### 6. Updated Entry Point (`monitor.py`)

```python
import os, yaml, time
from dotenv import load_dotenv

from bot import Account, Logger
from bot.modules.manager import ModuleManager


def load_config(file_path: str) -> dict:
    """Load the config file and the `.env` variables."""
    with open(file_path, "r") as f:
        config = yaml.safe_load(f)

    env_file_path = os.path.join(os.path.dirname(file_path), ".env")
    load_dotenv(env_file_path)

    config["env_vars"] = {
        key: value
        for key, value in os.environ.items()
        if key.startswith(("POSTGRES_", "STATUS_"))
    }

    return config


def create_bot(config: dict) -> Account:
    """Initialize a logged in bot account."""
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
    if account.info["compressed_key"] != config["bot"]["compressed_key"]:
        raise Exception("Target compressed key and logged in compressed key are different")

    account.profile_picture = os.path.join(os.path.dirname(__file__), "assets", "profile.jpg")
    account.logger.info(
        f"Account Information:\n"
        f"Compressed Key: {account.info['compressed_key']}\n"
        f"Public Key: {account.info['public_key']}\n"
        f"URL: {account.info['url']}"
    )
    return account


if __name__ == "__main__":
    folder = os.path.dirname(__file__)
    config = load_config(os.path.join(folder, "config.yaml"))
    logger = Logger()
    account = create_bot(config)

    # Initialize module manager
    manager = ModuleManager(config, account, logger)
    manager.discover_modules()
    manager.load_modules()
    manager.start_modules()

    try:
        manager.run_modules()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        manager.stop_modules()
```

### Phase 2: Main Refactor

1. Rewrite `monitor.py` as entry point
2. Move `download()` → `MonitoringModule`
3. Move `store()` → `StorageModule`

### Phase 3: Module System

1. Implement module discovery from directory
2. Add event-driven support via Signal class
3. Add error isolation (try/except per module)

### Phase 4: Testing & Docs

1. Create example custom module
2. Add module API documentation

## Backward Compatibility

- Keep `config.yaml` structure compatible (add `modules` section)
- Current functionality preserved as built-in modules
- Existing `.env` works unchanged

## Requirements from User

1. **Module flexibility**: Anyone should be able to create their own module (store messages, react to mentions, analytics, automated messages)
2. **Configuration**: Modules configured in config.yaml but loaded from directory
3. **Execution**: Independent modules (not sequential pipeline)
4. **Execution pattern**: Both periodic and event-driven support
5. **Interface**: BaseModule class with required methods
6. **Error handling**: Isolated (one module failure doesn't crash others)
7. **Shared resources**: Passed through constructor (Account, config, logger)
