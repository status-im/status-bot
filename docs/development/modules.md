# Modules

Modules are plugins that extend the bot with custom logic. Each module runs in its own daemon thread and follows a defined lifecycle.

---

## Module types

| Type | Behaviour | Use case |
|------|-----------|----------|
| `PERIODIC` | Calls `execute()` in a loop, sleeping `interval` seconds between runs | Scheduled data extraction, polling |
| `EVENT` | Iterates over WebSocket signal events, calling `on_event()` for each one | Real-time message reactions, auto-reply |
| `SERVICE` | Calls `execute()` once. Expected to block until shutdown (e.g. runs a server) | HTTP API server, long-running workers |

---

## BaseModule API

```python
from bot.modules.base import BaseModule, ModuleType

class MyModule(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.PERIODIC

    def on_start(self):
        ...  # called once when the module starts

    def execute(self):
        ...  # main logic (called periodically or once)

    def on_stop(self):
        ...  # called once when the module stops

    def on_event(self, event: dict):
        ...  # handle a signal event (EVENT type only)
```

### ModuleContext

Every module receives a `ModuleContext` via the constructor, accessible as `self.ctx`:

| Field | Type | Description |
|-------|------|-------------|
| `account` | `Account` | Logged-in Status account |
| `config` | `ModuleConfig` | This module's configuration |
| `logger` | `Logger` | Shared logger |
| `db` | `Postgres / None` | Optional Postgres connection |
| `shared_state` | `dict` | Cross-module shared data |
| `stop_event` | `threading.Event` | Set when the bot is shutting down |

### ModuleConfig

Each module receives only its own settings from `config.yaml`:

```python
self.ctx.config.name        # module identifier
self.ctx.config.interval    # seconds between PERIODIC runs
self.ctx.config.max_retries # restart attempts before permanent failure
self.ctx.config.settings    # dict of module-specific settings
```

---

## Adding API routes

Modules that want to expose HTTP endpoints can register routes on the shared FastAPI app instead of starting their own server.

The central `api_server` module owns the uvicorn lifecycle. Other modules register routes during `on_start()`:

```python
class MyAPIModule(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.SERVICE

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

The `api_server` module is auto-loaded whenever any API module is enabled and `api.enable` is `true`.

---

## Signals and EVENT modules

EVENT modules react to Status WebSocket signals:

```python
class AutoReplyModule(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.EVENT

    def on_start(self):
        self._commands = self.ctx.config.settings.get("commands", {})

    def on_event(self, event: dict):
        messages = event.get("event", {}).get("messages", [])
        for msg in messages:
            self.ctx.account.send_message(msg["chatId"], "Message received")
```

The signal listener respects `stop_event` for graceful shutdown.

---

## Utility functions

`bot/modules/utils.py` provides shared helpers:

| Function | Description |
|----------|-------------|
| `to_sha256_hash(value)` | Returns the SHA-256 hex digest of a string |
| `to_midnight(timestamp)` | Truncates a datetime to the start of its day |
| `save_file(file_path, data)` | Saves a DataFrame as CSV or pickles any other object |

---

## Best practices

- **Error isolation**: One module crash never affects others. The `ModuleManager` restarts failed modules with exponential backoff.
- **Graceful shutdown**: Always check `self.ctx.stop_event.is_set()` or use `self.ctx.stop_event.wait()` in long-running loops.
- **No blocking in EVENT modules**: EVENT handlers process one event at a time — keep `on_event()` fast.
- **Thread safety**: Modules run in separate threads. Use `shared_state` with caution for shared mutable data.
- **Configuration**: Read module-specific settings from `self.ctx.config.settings` — each module gets its own config namespace.
