# Modules

Modules extend the bot with custom logic. Each module runs in its own daemon thread and follows a defined lifecycle.

## Module types

Modules can declare one or more types. The behavior is composed from the declared types:

| Type | Behaviour |
|------|-----------|
| `PERIODIC` | Calls `execute()` in a loop, sleeping `interval` minutes between runs |
| `EVENT` | Receives messages via `on_event()` (centralized listener) |
| `SERVICE` | Calls `execute()` once. Expected to block until shutdown |

**Combination examples:**
- `PERIODIC | EVENT`: Runs `execute()` periodically and receives signal events
- `EVENT | SERVICE`: Listens to events while running a blocking service

## Module layout

A module is either a **single file** or a **directory**, discovered in the bot package itself and in every directory listed in `modules.directories`:

```
modules/
├── my_module.py            # single-file module
└── my_other_module/        # directory module
    ├── main.py             # entry point (required)
    ├── helpers.py          # sibling file, importable from main.py
    └── models.py
```

- The module **name** is the file name or directory name (`my_module`, `my_other_module`); it is the identifier used in `enabled`, `settings`, and the module YAML file.
- Directory modules load `main.py` as the entry point. Sibling files can be imported from `main.py` (and from other sibling files) with **plain imports** (`import helpers`, `from helpers import x`) and with **relative imports** (`from .helpers import x`) — both work.
- Files and directories starting with `_` are ignored, as are the framework files `base.py`, `manager.py`, and `utils.py`.
- If both `module-name.py` and `module-name/main.py` exist in the same scanned directory, the **directory version is loaded** and a warning is logged.
- Sibling files are put on `sys.path`, so a sibling named like a stdlib or `status_bot` module would shadow it — avoid such names.

## Module configuration

Each module's settings come from `self.ctx.config.settings` (see below), which is resolved from up to two YAML sources:

1. `modules.settings.<module-name>` in the main `config.yaml`
2. `<config_directory>/<module-name>.yaml`, where `config_directory` is set via `modules.config_directory`

The two are **deep-merged**: nested dicts are merged key by key and the module YAML wins on conflicting keys; non-conflicting `config.yaml` keys are kept.
Environment variables (`MODULES__SETTINGS__<MODULE>__<KEY>`) still have the highest priority. 
Overall precedence, highest first:

1. env vars
2. config_directory>/<module-name>.yaml
3. config.yaml

A malformed module YAML is logged as an error and the module starts with its `config.yaml` settings only.

## BaseModule API

```python
from status_bot.modules.base import BaseModule, ModuleType
from status_sdk.models import Message

class MyModule(BaseModule):

    @property
    def module_type(self) -> set[ModuleType]:
        return {ModuleType.PERIODIC}

    def on_start(self):
        ...  # called once when the module starts

    def execute(self):
        ...  # main logic (called periodically or once)

    def on_stop(self):
        ...  # called once when the module stops

    def on_event(self, message: Message):
        ...  # handle a received message (EVENT type only)

    def register_metrics(self):
        ...  # optional: register Prometheus metrics
```
### Properties

#### `interval`

Number of minutes to wait between every `ModuleType.PERIODIC` run. This value can be set within the module config `modules.settings.$module_name.interval` or in the module's own YAML file (`<config_directory>/<module_name>.yaml`).

#### `db_schema`

The schema name you can upload data to.

#### `account`

Logged in Status account that can be used within the module.

#### `logger`

Set up logger that can be used within modules.

#### `name`

Module name (from configuration).

#### `settings`

Module-specific settings dictionary, deep-merged from `config.yaml` (`modules.settings.$module_name`) and the module's own YAML file (`<config_directory>/<module_name>.yaml`), the module YAML winning on conflicts — see [Module configuration](#module-configuration).

#### `ctx`

Every module receives a `ModuleContext` via the constructor, accessible as `self.ctx`:

| Field | Type | Description |
|-------|------|-------------|
| `account` | `Account` | Logged-in Status account |
| `config` | `ModuleConfig` | This module's configuration |
| `db` | `Database / None` | Optional database connection (Postgres or SQLite) |
| `shared_state` | `dict` | Cross-module shared data |
| `stop_event` | `threading.Event` | Set when the bot is shutting down |

##### `ModuleConfig`

Each module receives only its own settings (from `config.yaml` and its module YAML file):

```python
self.ctx.config.name        # module identifier
self.ctx.config.interval    # minutes between PERIODIC runs
self.ctx.config.max_retries # restart attempts before permanent failure
self.ctx.config.settings    # dict of module-specific settings
```

#### `_mandatory_properties`

List of keys that must be present in the module configuration.
The presence of properties is checked at the start of the module.

## Adding API routes

Modules that want to expose HTTP endpoints can register routes on the shared FastAPI app instead of starting their own server.

The central `api_server` module owns the uvicorn lifecycle. Other modules register routes during `on_start()`:

```python
class MyAPIModule(BaseModule):

    @property
    def module_type(self) -> set[ModuleType]:
        return {ModuleType.SERVICE}

    def on_start(self):
        app = self.ctx.shared_state["fastapi_app"]
        self._setup_routes(app)

    def _setup_routes(self, app):
        @app.get("/api/v1/my-endpoint")
        def my_handler():
            return {"hello": "world"}

    def execute(self):
        self.ctx.stop_event.wait()  # block until shutdown
```

The `api_server` module is auto-loaded whenever `api.enable` is `true` — it does not need to be listed in `enabled`.


## Signals and EVENT modules

Modules declaring `ModuleType.EVENT` in their `module_type` set receive every incoming message as a `status_sdk` `Message` object via `on_event()`. The centralized signal listener (`Account.listen_messages()`) delivers the messages to all such modules.

```python
class AutoReplyModule(BaseModule):

    @property
    def module_type(self) -> set[ModuleType]:
        return {ModuleType.EVENT}

    def on_start(self):
        self._commands = self.ctx.config.settings.get("commands", {})

    def on_event(self, message: Message):
        self.ctx.account.send_message(message.chat_id, "Message received")
```

A module can declare `EVENT` alongside other types (e.g., `PERIODIC | EVENT`). In that case, it both receives signal events and has its `execute()` called periodically. The signal listener respects `stop_event` for graceful shutdown.


## Utility functions

`status_bot/modules/utils.py` provides shared helpers:

| Function | Description |
|----------|-------------|
| `to_sha256_hash(value)` | Returns the SHA-256 hex digest of a string |
| `derive_encryption_key(secret)` | Derives the AES-SIV key from `bot.encryption_key`: a hex/base64 encoded 32/48/64 byte value is used directly, any other value is stretched with PBKDF2-HMAC-SHA256. Warns once when the secret is empty |
| `to_encrypted_value(value, key)` | Encrypts a string with AES-SIV (deterministic, authenticated) and returns it with an `enc1$` prefix |
| `from_encrypted_value(value, key)` | Decrypts a value produced by `to_encrypted_value`; raises `ValueError` on tampering or a wrong key |
| `to_midnight(timestamp)` | Truncates a datetime to the start of its day |


## Message storage & privacy

The `receiver` module persists received messages (as `status_sdk` `Message` objects) to the configured database. Before insertion, identifying and content-bearing fields are encrypted with `to_encrypted_value` (AES-256-SIV, key derived from `bot.encryption_key`) so no human-readable user data is stored at rest:

- **Messages — deterministic (AES-SIV, no nonce):** `id`, `from`, `response_to`, `chat_id`, `text`. `id` stays stable so primary-key dedup keeps working.
- `content_type` is stored as its integer value (`Content` enum unwrapped), `chat_type` as the enum member name (`PRIVATE`/`GROUP`/`COMMUNITY`) in `message_type`.
- Columns without a counterpart on `Message` (`alias`, `contact_request_state`, `compressed_key`) stay `NULL`.

The event payload is never modified — plaintext remains available in-memory for handling; only the persisted copy is encrypted. Rows written by versions that used HMAC-SHA256 hashing are not decryptable and must be purged (see [Privacy & storage](../deployment/configuration.md#privacy--storage)).


## Best practices

- **Error isolation**: One module crash never affects others. The `ModuleManager` restarts failed modules with exponential backoff.
- **Graceful shutdown**: Always check `self.ctx.stop_event.is_set()` or use `self.ctx.stop_event.wait()` in long-running loops.
- **No blocking in EVENT modules**: EVENT handlers process one event at a time — keep `on_event()` fast.
- **Thread safety**: Modules run in separate threads. Use `shared_state` with caution for shared mutable data.
- **Configuration**: Read module-specific settings from `self.ctx.config.settings` — each module gets its own config namespace.
