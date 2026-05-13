# Refactoring Plan: Status Bot Modular Architecture

> This document captures the full context, design decisions, and step-by-step
> implementation plan for transforming `monitor.py` into a modular plugin-based
> system. It is designed to be self-contained so the refactoring can span
> multiple sessions.

---

## Table of Contents

1. [Current Architecture](#1-current-architecture)
2. [Issues with the Current Codebase](#2-issues-with-the-current-codebase)
3. [Target Architecture](#3-target-architecture)
4. [Module System Design](#4-module-system-design)
   - 4.1 ModuleType
   - 4.2 ModuleConfig
   - 4.3 ModuleContext
   - 4.4 BaseModule (ABC)
   - 4.5 ModuleManager
5. [Threading & Lifecycle](#5-threading--lifecycle)
6. [Error Handling & Retry](#6-error-handling--retry)
7. [Configuration Shape](#7-configuration-shape)
8. [Prometheus Metrics](#8-prometheus-metrics)
9. [Signal.listen() Graceful Shutdown](#9-signallisten-graceful-shutdown)
10. [Implementation Steps](#10-implementation-steps)
    - [Step 1: Core Framework + Entry Point](#step-1-core-framework--entry-point)
    - [Step 2: Refactor monitor.py → MonitoringModule](#step-2-refactor-monitorpy--monitoringmodule)
    - [Step 3: Connection Pool + Retry Logic](#step-3-connection-pool--retry-logic)
    - [Step 4: Example Event-Driven Module](#step-4-example-event-driven-module)
    - [Step 5: Tests + Documentation](#step-5-tests--documentation)
11. [File-by-File Summary](#11-file-by-file-summary)

---

## 1. Current Architecture

```
/repos/status-bot/
├── bot/
│   ├── __init__.py        # Exports Account and Logger
│   ├── account.py         # Account class — Status Backend API wrapper (1112 lines)
│   ├── signal.py          # Signal class — WebSocket handler for Status signals
│   ├── logger.py          # Logger singleton
│   └── requirements.txt
├── modules/               # (does not exist yet)
├── accounts/
├── assets/
├── data-dir/              # Status Backend runtime data
├── docs/
├── tests/                 # Empty
├── monitor.py             # Main entry point — 316-line monolithic script
├── postgres.py            # Postgres connector
├── config.yaml
├── Dockerfile
├── docker-compose.yaml
├── module-refactoring.md  # Initial draft (superseded by this document)
└── README.md
```

### Current Flow

`monitor.py` does everything in one file:
1. Config loading (`load_config`)
2. Bot creation (`create_bot`)
3. Community data extraction (`download`)
4. Data storage / upload (`store`)
5. Main loop (while True: download → store → sleep)

### SDK Layer (`bot/`)

The `bot/` package is well-structured and reusable:
- **`Account`** — wraps Status Backend HTTP / RPC / WebSocket APIs
- **`Signal`** — WebSocket event handling (single-get + streaming)
- **`Logger`** — singleton logging

These should remain largely unchanged.

---

## 2. Issues with the Current Codebase

| Issue | Description |
|-------|-------------|
| **Monolithic** | `monitor.py` combines config, bot init, extraction, storage, and cleanup in one file |
| **Hardcoded pipeline** | `download()` then `store()` — no way to run independently or add middleware |
| **Tight coupling** | `store()` knows about pickle format from `download()`; `latest_dates` is shared implicitly |
| **No error isolation** | One failure can corrupt state (files deleted mid-failure) |
| **Untestable** | Global functions reference filesystem directly; no mocking boundary |
| **No concurrency** | Single-threaded loop — if monitor sleeps 10 min, auto-reply can't react |
| **SQL injection risk** | `postgres.py` uses f-strings for schema/table/column identifiers |
| **No module system** | Adding a new feature means either bloating `monitor.py` or duplicating init code |
| **No graceful shutdown** | No SIGTERM handler; `Account.__del__` is unreliable in Docker |

---

## 3. Target Architecture

```
main.py ────────────────────────────────────────────────────────┐
  │  - Load config.yaml & .env                                    │
  │  - Create Account (login)                                     │
  │  - Create Postgres (connection pool)                          │
  │  - Init ModuleManager(config, account, db, logger)            │
  │  - manager.start_all() → returns immediately                  │
  │  - Start Prometheus HTTP endpoint (/metrics)                  │
  │  - signal.signal(SIGTERM) → manager.stop_all()                │
  │  - Wait forever (or until all modules die)                    │
  └───────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │      ModuleManager         │
              │  - discover_modules()      │
              │  - load_modules()          │
              │  - start_all() → threads   │
              │  - stop_all() → join       │
              └─────────────┬──────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
  MonitoringModule    AutoReplyModule     (user modules)
  (PERIODIC, thread)  (EVENT, thread)     ...
         │                  │
         │  while running:  │  for event in
         │    download()    │  signal.listen():
         │    store()       │    on_event()
         │    sleep(N)      │
```

### Directory Layout After Refactoring

```
status-bot/
├── bot/                           # SDK layer (minimal changes)
│   ├── __init__.py
│   ├── account.py
│   ├── signal.py                  # ← modified: listen() accepts stop_event
│   ├── logger.py
│   └── modules/                   # ← NEW: module framework
│       ├── __init__.py
│       ├── base.py                # BaseModule, ModuleType, ModuleConfig, ModuleContext
│       ├── manager.py             # ModuleManager
│       └── utils.py               # Shared helpers (to_sha256_hash, etc.)
│
├── modules/                       # ← NEW: user-space modules
│   ├── __init__.py
│   ├── monitoring.py              # MonitoringModule (extracted from monitor.py)
│   └── auto_reply.py              # Example event-driven module
│
├── main.py                        # ← NEW: entry point
├── postgres.py                    # ← modified: connection pool
├── config.yaml                    # ← modified: + modules: + prometheus: sections
├── Dockerfile                     # ← modified: ENTRYPOINT → main.py
│
├── tests/
│   ├── test_base.py
│   ├── test_manager.py
│   └── test_monitoring_module.py
│
└── docs/
    └── refactoring-module-plan.md # This document
```

---

## 4. Module System Design

### 4.1 ModuleType (Enum)

Defines how a module is executed by the manager.

```python
class ModuleType(Enum):
    PERIODIC = "periodic"   # Runs execute() on a fixed interval in its own thread
    EVENT    = "event"      # Reacts to Signal events via on_event() callback
    SERVICE  = "service"    # Runs once and keeps running (blocking)
```

| Type | Execution | Example |
|------|-----------|---------|
| `PERIODIC` | Thread loop: `execute()` → sleep(interval) | Monitoring, Storage |
| `EVENT` | Thread: `for event in signal.listen(stop_event): on_event(event)` | Auto-reply, Mentions |
| `SERVICE` | Thread: `execute()` runs forever | WebSocket listener |

### 4.2 ModuleConfig (Dataclass)

Configuration for a single module. Each module receives only its own config, not the full config.yaml.

```python
@dataclass
class ModuleConfig:
    name: str                        # Module identifier (matches config key)
    enabled: bool = True
    interval: int = 60               # For PERIODIC modules (seconds)
    max_retries: int = 3             # Max restart attempts before permanent failure
    backoff_seconds: int = 30        # Wait between restarts (doubles each attempt)
    settings: dict = None            # Module-specific arbitrary settings

    def __post_init__(self):
        if self.settings is None:
            self.settings = {}
```

### 4.3 ModuleContext (Dataclass)

Shared dependencies injected into every module. Wrapping in a single dataclass makes it easy to add new shared resources later without changing module constructors.

```python
@dataclass
class ModuleContext:
    account: "Account"               # Logged-in Status bot account
    config: ModuleConfig             # This module's config only
    logger: logging.Logger           # Shared logger
    db: Optional["Postgres"] = None  # Database connection (optional)
    shared_state: dict = field(default_factory=dict)  # Cross-module state
    stop_event: threading.Event = None  # Signal for graceful shutdown
```

### 4.4 BaseModule (ABC)

```python
class BaseModule(ABC):

    def __init__(self, ctx: ModuleContext):
        self._ctx = ctx
        self._running = False

    # --- Properties ---

    @property
    def ctx(self) -> ModuleContext:
        return self._ctx

    @property
    @abstractmethod
    def module_type(self) -> ModuleType:
        """Return the execution type of this module."""
        ...

    @property
    def name(self) -> str:
        return self._ctx.config.name

    # --- Lifecycle ---

    @abstractmethod
    def execute(self) -> Any:
        """
        Main logic. Called periodically (PERIODIC), once (SERVICE),
        or not at all for EVENT modules.
        """
        ...

    def on_start(self) -> None:
        """Called once when the module starts. Override for init logic."""

    def on_stop(self) -> None:
        """Called once when the module stops. Override for cleanup."""

    def on_event(self, event: dict) -> Any:
        """Handle a Signal event (for EVENT type modules)."""

    # --- Internal ---

    @property
    def is_running(self) -> bool:
        return self._running
```

### 4.5 ModuleManager

```python
class ModuleManager:

    def __init__(self, config: dict, account: Account, db: Optional[Postgres], logger: Logger):
        self._config = config          # Full config (for module settings extraction)
        self._account = account
        self._db = db
        self._logger = logger
        self._modules: dict[str, BaseModule] = {}
        self._module_classes: dict[str, Type[BaseModule]] = {}
        self._threads: dict[str, Thread] = {}
        self._stop_event = threading.Event()

    def discover_modules(self) -> None:
        """Scan configured directories for BaseModule subclasses."""
        for directory in self._config["modules"]["directories"]:
            for py_file in Path(directory).glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                # importlib: spec → module → find BaseModule subclasses
                # Store in self._module_classes[file_stem] = class

    def load_modules(self) -> None:
        """Instantiate only the enabled modules."""
        for module_name in self._config["modules"]["enabled"]:
            cls = self._module_classes.get(module_name)
            if not cls:
                self._logger.error(f"Module '{module_name}' not found")
                continue
            settings = self._config["modules"]["settings"].get(module_name, {})
            module_config = ModuleConfig(
                name=module_name,
                interval=settings.get("interval", 60),
                max_retries=settings.get("max_retries", 3),
                backoff_seconds=settings.get("backoff_seconds", 30),
                settings=settings,
            )
            ctx = ModuleContext(
                account=self._account,
                config=module_config,
                logger=self._logger,
                db=self._db,
                stop_event=self._stop_event,
            )
            self._modules[module_name] = cls(ctx)

    def start_all(self) -> None:
        """Start all modules in their own threads. Returns immediately."""
        for name, module in self._modules.items():
            t = Thread(target=self._run_module_wrapper, args=(module,), daemon=True)
            self._threads[name] = t
            t.start()

    def stop_all(self) -> None:
        """Trigger graceful shutdown of all modules."""
        self._stop_event.set()
        for name, t in self._threads.items():
            t.join(timeout=5)

    def _run_module_wrapper(self, module: BaseModule) -> None:
        """Run a single module with retry/backoff logic (see Section 6)."""
        ...
```

---

## 5. Threading & Lifecycle

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Concurrency | `threading.Thread` | Simple, works with blocking I/O, no asyncio refactor needed |
| Shutdown signal | `threading.Event` | Thread-safe, all loops check it |
| SIGTERM handling | `signal.signal(SIGTERM, handler)` | Required for Docker `docker stop` |
| Manager return | Returns immediately | `main.py` owns the wait / signal handling |
| Daemon threads | `daemon=True` | Prevents hanging if stop_all() hangs |

### Lifecycle Diagram

```
main.py
  │
  ├── load_config()
  ├── Account().login()
  ├── Postgres()
  ├── ModuleManager(config, account, db, logger)
  ├── manager.discover_modules()
  ├── manager.load_modules()
  │
  ├── manager.start_all()
  │    ├── Thread(MONITORING).start()
  │    ├── Thread(AUTO_REPLY).start()
  │    └── returns immediately
  │
  ├── start Prometheus HTTP server (thread or daemon)
  │
  ├── signal.signal(SIGTERM, handler)
  │    └── handler → manager.stop_all()
  │
  └── wait (threading.Event().wait() or while True: sleep)
```

### Thread-per-Module: PERIODIC

```python
def _run_module_wrapper(self, module: BaseModule):
    try:
        module.on_start()
    except Exception:
        ...  # handle

    if module.module_type == ModuleType.PERIODIC:
        while not self._stop_event.is_set():
            try:
                module.execute()
            except Exception:
                ...  # retry/backoff (see Section 6)
            self._stop_event.wait(module.interval)
```

### Thread-per-Module: EVENT

```python
    elif module.module_type == ModuleType.EVENT:
        for event in self._account.signal.listen("messages.new", stop_event=self._stop_event):
            if self._stop_event.is_set():
                break
            try:
                module.on_event(event)
            except Exception:
                ...  # log, don't crash
```

### Thread-per-Module: SERVICE

```python
    elif module.module_type == ModuleType.SERVICE:
        try:
            module.execute()  # blocking — runs until stop
        except Exception:
            ...  # retry/backoff
```

---

## 6. Error Handling & Retry

### Principles

1. **Error isolation**: One module crash never brings down another module or the bot.
2. **Retry with backoff**: Failed modules are restarted with exponential backoff.
3. **Permanent failure**: After `max_retries` consecutive failures, the module is marked dead and not restarted.
4. **Bot survival**: The bot stops only if:
   - It cannot log in to the Status account (fatal).
   - No module started successfully (all modules are permanently dead).
   - A module can be dead while others continue running.

### Retry Logic in `_run_module_wrapper`

```python
def _run_module_wrapper(self, module: BaseModule):
    retries = 0
    max_retries = module.ctx.config.max_retries
    backoff = module.ctx.config.backoff_seconds

    while retries <= max_retries and not self._stop_event.is_set():
        try:
            module._running = True
            module.on_start()

            if module.module_type == ModuleType.PERIODIC:
                while not self._stop_event.is_set():
                    module.execute()
                    self._stop_event.wait(module.interval)
            elif module.module_type == ModuleType.EVENT:
                for event in self._account.signal.listen("messages.new", stop_event=self._stop_event):
                    if self._stop_event.is_set():
                        break
                    module.on_event(event)
            elif module.module_type == ModuleType.SERVICE:
                module.execute()

            # If we get here without exception, module exited cleanly
            break

        except Exception as e:
            retries += 1
            self._logger.error(
                f"Module '{module.name}' failed ({retries}/{max_retries}): {e}"
            )
            if retries <= max_retries:
                wait = backoff * (2 ** (retries - 1))  # exponential backoff
                self._logger.info(f"Restarting '{module.name}' in {wait}s...")
                self._stop_event.wait(wait)
            else:
                self._logger.error(f"Module '{module.name}' permanently failed.")
        finally:
            module._running = False
            try:
                module.on_stop()
            except Exception:
                pass
```

### config.yaml settings for retry

```yaml
modules:
  settings:
    monitoring:
      interval: 600
      max_retries: 3
      backoff_seconds: 30
    auto_reply:
      max_retries: 3
      backoff_seconds: 10
```

---

## 7. Configuration Shape

### Guiding Principles

- **Do not modify existing keys** — `postgres:`, `sleep:`, `files:`, `bot:` stay exactly as they are.
- **Add new sections only**: `modules:` and `prometheus:`.
- Each module gets its own sub-section under `modules.settings.<name>`.
- Each module receives only its own `ModuleConfig` (not the full config).

### Final `config.yaml`

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
    public_key: "0x..."
    compressed_key: "zQ3..."
    params:
        domain: "status-backend"
        port: 8080
        is_secure: false

# ===== NEW SECTIONS BELOW =====

modules:
    directories:
        - ./modules
    enabled:
        - monitoring
    settings:
        monitoring:
            interval: 600          # seconds between runs
            max_retries: 3
            backoff_seconds: 30
        auto_reply:
            max_retries: 3
            backoff_seconds: 10
            commands:
                help: "!help"
                status: "!status"

prometheus:
    enabled: true
    host: "0.0.0.0"
    port: 8000
```

### How `main.py` extracts module configs

```python
modules_config = config.get("modules", {})
enabled = modules_config.get("enabled", [])
settings = modules_config.get("settings", {})

for module_name in enabled:
    module_settings = settings.get(module_name, {})
    module_config = ModuleConfig(
        name=module_name,
        interval=module_settings.get("interval", 60),
        max_retries=module_settings.get("max_retries", 3),
        backoff_seconds=module_settings.get("backoff_seconds", 30),
        settings=module_settings,
    )
```

---

## 8. Prometheus Metrics

### Endpoint

A simple HTTP server on a configurable `host:port` (default `0.0.0.0:8000`)
serving `/metrics` in Prometheus text format using the `prometheus_client` library.

### Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `status_bot_health` | Gauge | — | 1 if running, 0 if stopped |
| `status_bot_version` | Gauge | `version` | Version info (constant 1 with label) |
| `status_bot_module_loaded` | Gauge | `module` | 1 for each loaded module |
| `status_bot_module_errors_total` | Counter | `module` | Total error count per module |
| `status_bot_module_restarts_total` | Counter | `module` | Total restart count per module |

### Implementation in `main.py`

```python
from prometheus_client import start_http_server, Gauge, Counter

def start_prometheus_server(config: dict, manager: ModuleManager):
    prom_config = config.get("prometheus", {})
    if not prom_config.get("enabled", False):
        return

    health = Gauge("status_bot_health", "Bot health status")
    version = Gauge("status_bot_version", "Bot version", ["version"])
    module_loaded = Gauge("status_bot_module_loaded", "Module loaded", ["module"])
    module_errors = Counter("status_bot_module_errors_total", "Module errors", ["module"])
    module_restarts = Counter("status_bot_module_restarts_total", "Module restarts", ["module"])

    health.set(1)
    version.labels(version="0.1.0").set(1)
    for module_name in manager.modules:
        module_loaded.labels(module=module_name).set(1)

    host = prom_config.get("host", "0.0.0.0")
    port = prom_config.get("port", 8000)
    start_http_server(port, host)
```

### Dependency

Add `prometheus-client` to `requirements.txt`.

---

## 9. Signal.listen() Graceful Shutdown

### Problem

The current `Signal.listen()` blocks forever on `queue.get()` with no timeout:

```python
# Current (blocks forever):
while True:
    data = self.__queue.get()       # ← blocks indefinitely
    yield data
```

This means an EVENT-type module thread can never be stopped cleanly —
`stop_event.set()` is never checked.

### Solution

Add an optional `stop_event: threading.Event` parameter to `listen()`.
Replace `queue.get()` with `queue.get(timeout=1)` in a loop that checks
the event:

```python
# Modified:
def listen(self, signal_type: str, stop_event: Optional[threading.Event] = None):
    self.__signal_type = signal_type
    ws = websocket.WebSocketApp(...)
    self.__thread = threading.Thread(target=ws.run_forever, daemon=True)
    self.__thread.start()

    while True:
        try:
            data = self.__queue.get(timeout=1)  # ← non-blocking with timeout
        except queue.Empty:
            if stop_event and stop_event.is_set():
                break
            continue
        except KeyboardInterrupt:
            break
        if self.__error_message:
            raise Exception(self.__error_message)
        yield data
```

### Changes to `bot/signal.py`

- Add `import threading` (already imported)
- Change `listen(self, signal_type: str)` → `listen(self, signal_type: str, stop_event: Optional[threading.Event] = None)`
- Replace `self.__queue.get()` with the timeout loop above

---

## 10. Implementation Steps

### Step 1: Core Framework + Entry Point

**Goal**: Create the module framework and a working `main.py` entry point.
No existing monitoring functionality is moved yet — `modules.enabled` would be
empty, and the bot starts with no modules (or a placeholder).

**Files to create:**

| File | Content |
|------|---------|
| `bot/modules/__init__.py` | Empty package marker |
| `bot/modules/base.py` | `ModuleType` Enum, `ModuleConfig` dataclass, `ModuleContext` dataclass, `BaseModule` ABC |
| `bot/modules/manager.py` | `ModuleManager` class with `discover_modules()`, `load_modules()`, `start_all()` (threaded), `stop_all()`, `_run_module_wrapper()` with retry/backoff |
| `main.py` | New entry point — config loading, bot creation, DB init, manager init, Prometheus server, signal handlers |

**Files to modify:**

| File | Change |
|------|--------|
| `bot/signal.py` | Add `stop_event` parameter to `listen()` (see [Section 9](#9-signallisten-graceful-shutdown)) |
| `config.yaml` | Add `modules:` and `prometheus:` sections |
| `Dockerfile` | Change `ENTRYPOINT ["python", "main.py"]` |
| `requirements.txt` | Add `prometheus-client` |

**Files to delete:**

| File | Reason |
|------|--------|
| `module-refactoring.md` | Superseded by this document |

**Verification:**

```bash
# Without any modules enabled, the bot should:
# 1. Load config
# 2. Log in
# 3. Start Prometheus endpoint
# 4. Wait for SIGTERM
python main.py
```

---

### Step 2: Refactor monitor.py → MonitoringModule

**Goal**: Extract the community monitoring logic from `monitor.py` into a
proper `MonitoringModule` under `./modules/`. Delete the old `monitor.py`.

**Files to create:**

| File | Content |
|------|---------|
| `modules/__init__.py` | Empty package marker |
| `modules/monitoring.py` | `MonitoringModule(BaseModule)` — PERIODIC type, calls `execute()` which runs `_download()` + `_store()` |
| `bot/modules/utils.py` | Shared helpers extracted from `monitor.py`: `to_sha256_hash()`, `to_midnight()`, `save_file()`, `extract_community_channels()` |

**What goes where in `modules/monitoring.py`:**

| Original function in `monitor.py` | New home |
|-----------------------------------|----------|
| `load_config()` | Stays in `main.py` |
| `create_bot()` | Stays in `main.py` |
| `to_sha256_hash()` | `bot/modules/utils.py` |
| `to_midnight()` | `bot/modules/utils.py` |
| `save_file()` | `bot/modules/utils.py` |
| `extract_community_channels()` | `bot/modules/utils.py` or private to MonitoringModule |
| `download()` | `MonitoringModule._download()` |
| `store()` | `MonitoringModule._store()` |
| `if __name__ == "__main__":` block | Deleted (replaced by `main.py`) |

**Behavior**: The module receives `Postgres` via `ModuleContext.db`. It reads
`monitoring`-specific settings from `ModuleContext.config.settings`.

**Verification:**

```bash
# With monitoring enabled in config.yaml:
# The bot should download community data and store to Postgres.
python main.py
```

---

### Step 3: Connection Pool + Retry Logic

**Goal**: Make `Postgres` thread-safe with a connection pool, and verify the
retry/backoff logic in `ModuleManager` works.

**Files to modify:**

| File | Change |
|------|--------|
| `postgres.py` | Refactor to use `sqlalchemy.create_engine` with connection pooling (pool_size=5, max_overflow=10). Ensure `pandas.to_sql()` reuses the same engine. |
| `bot/modules/manager.py` | Retry/backoff logic should already be implemented in Step 1. Verify and test edge cases. |

**Connection pool approach:**

```python
class Postgres:
    def __init__(self, ...):
        self._engine = create_engine(
            self.__url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # verify connections before use
        )

    def insert(self, data, table_name, schema, json_columns=None):
        # Use self._engine.begin() for transaction management
        ...

    def to_pandas(self, query):
        return pd.read_sql(query, self._engine)
```

**Verification:**

```bash
# Run with multiple modules enabled; verify concurrent DB access works.
python main.py
```

---

### Step 4: Example Event-Driven Module

**Goal**: Create an `AutoReplyModule` to demonstrate the event-driven pattern
for future module developers.

**Files to create:**

| File | Content |
|------|---------|
| `modules/auto_reply.py` | `AutoReplyModule(BaseModule)` — EVENT type, listens for `messages.new`, checks for `!help` / `!status` commands, replies with configured responses |

**`modules/auto_reply.py` structure:**

```python
class AutoReplyModule(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.EVENT

    def on_start(self):
        self._commands = self._ctx.config.settings.get("commands", {})
        self._logger.info(f"Auto-reply loaded with commands: {list(self._commands.keys())}")

    def on_event(self, event: dict):
        messages = event.get("event", {}).get("messages", [])
        for msg in messages:
            text = msg.get("text", "")
            for cmd_name, cmd_text in self._commands.items():
                if text.strip().lower() == cmd_text.lower():
                    response = self._build_response(cmd_name, msg)
                    self._account.send_message(msg["chatId"], response)

    def _build_response(self, command_name, message):
        # Module-specific reply logic
        ...
```

**Verification:**

```bash
# Enable auto_reply in config.yaml, send a message with "!help" to the bot.
```

---

### Step 5: Tests + Documentation

**Goal**: Ensure the framework is reliable and documented.

**Files to create:**

| File | Content |
|------|---------|
| `tests/test_base.py` | Test `ModuleConfig`, `ModuleContext`, `BaseModule` subclass contract |
| `tests/test_manager.py` | Mock `Account` and test discovery, loading, thread start/stop |
| `tests/test_monitoring_module.py` | Test `MonitoringModule` with mocked account and DB |

**Files to modify:**

| File | Change |
|------|--------|
| `README.md` | Document module API, how to write a module, directory structure |

**Test approach:**

```python
# test_base.py
def test_module_config_defaults():
    cfg = ModuleConfig(name="test")
    assert cfg.enabled == True
    assert cfg.interval == 60
    assert cfg.max_retries == 3

# test_manager.py
def test_discover_modules(tmp_path):
    # Create a mock module file
    module_file = tmp_path / "test_mod.py"
    module_file.write_text("""
from bot.modules.base import BaseModule, ModuleType
class TestModule(BaseModule):
    @property
    def module_type(self): return ModuleType.PERIODIC
    def execute(self): pass
""")
    manager = ModuleManager({"modules": {"directories": [str(tmp_path)], "enabled": []}}, mock_account, None, logger)
    manager.discover_modules()
    assert "test_mod" in manager._module_classes
```

---

## 11. File-by-File Summary

### New Files (8)

| # | Path | Step |
|---|------|------|
| 1 | `bot/modules/__init__.py` | 1 |
| 2 | `bot/modules/base.py` | 1 |
| 3 | `bot/modules/manager.py` | 1 |
| 4 | `main.py` | 1 |
| 5 | `modules/__init__.py` | 2 |
| 6 | `bot/modules/utils.py` | 2 |
| 7 | `modules/monitoring.py` | 2 |
| 8 | `modules/auto_reply.py` | 4 |
| 9 | `tests/test_base.py` | 5 |
| 10 | `tests/test_manager.py` | 5 |
| 11 | `tests/test_monitoring_module.py` | 5 |

### Modified Files (5)

| # | Path | Change |
|---|------|--------|
| 1 | `bot/signal.py` | Step 1: `listen()` accepts `stop_event` |
| 2 | `config.yaml` | Step 1: add `modules:` + `prometheus:` sections |
| 3 | `Dockerfile` | Step 1: change `ENTRYPOINT` to `main.py` |
| 4 | `requirements.txt` | Step 1: add `prometheus-client` |
| 5 | `README.md` | Step 5: update documentation |

### Deleted Files (2)

| # | Path | Reason |
|---|------|--------|
| 1 | `module-refactoring.md` | Superseded by this document |
| 2 | `monitor.py` | Step 2: logic moved to `modules/monitoring.py` |

---

## Appendix: Key References

- **`bot/account.py`** — ~1112 lines, wraps Status Backend HTTP/RPC API
- **`bot/signal.py`** — WebSocket handler; `listen()` will be modified for `stop_event`
- **`bot/logger.py`** — Singleton logger, 24 lines
- **`postgres.py`** — Postgres connector, 149 lines; needs connection pool refactor
- **`monitor.py`** — 316 lines, to be deleted after Step 2
