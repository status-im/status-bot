# Metrics

The bot exposes Prometheus metrics for health monitoring and observability.

---

## Endpoint

```
http://<prometheus_host>:<prometheus_port>/metrics
```

Default: `http://0.0.0.0:8000/metrics`

Configured via the `metrics` section in `config.yaml` (see [Configuration](./configuration.md#metrics)).

---

## Basic metrics

### `status_bot_health`

| Type | Labels | Description |
|------|--------|-------------|
| Gauge | — | `1` if the bot is running, `0` if stopped |

### `status_bot_version`

| Type | Labels | Description |
|------|--------|-------------|
| Gauge | `version` | Constant `1` with the bot version as a label value |

### `status_bot_module_loaded`

| Type | Labels | Description |
|------|--------|-------------|
| Gauge | `module` | `1` for each loaded module |

Example:
```
status_bot_module_loaded{module="messaging"} 1
status_bot_module_loaded{module="api_server"} 1
```

### `status_bot_module_execution_error`

| Type | Labels | Description |
|------|--------|-------------|
| Counter | `module` | Total number of errors encountered while running a module |

### `status_bot_module_execution`

| Type | Labels | Description |
|------|--------|-------------|
| Counter | `module` | Total number of periodic executions per module |

### `status_bot_module_start`

| Type | Labels | Description |
|------|--------|-------------|
| Counter | `module` | Total number of (re)start attempts after a module failure |

---

## API metrics

Registered by the `api_server` module. Like all module metrics they only exist
when `metrics.enabled` is `true`, and they cover **every** route served by the
shared FastAPI app — including routes added by other modules such as
`messaging`.

### `status_bot_api_requests_total`

| Type | Labels | Description |
|------|--------|-------------|
| Counter | `module`, `method`, `path`, `status` | Total HTTP requests handled by the API |

### `status_bot_api_request_duration_seconds`

| Type | Labels | Description |
|------|--------|-------------|
| Histogram | `module`, `method`, `path` | Request latency in seconds |

### `status_bot_api_auth_failures_total`

| Type | Labels | Description |
|------|--------|-------------|
| Counter | `module` | Requests rejected by the API key middleware (HTTP 401) |

`path` is the route *template* (e.g. `/api/v1/chats/{chat_id}/messages`), so
label cardinality stays bounded. Requests that match no route (404s) and
requests rejected before routing (401s) are labeled `path="unmatched"`.

Example:
```
status_bot_api_requests_total{module="api_server",method="GET",path="/health",status="200"} 1
status_bot_api_requests_total{module="api_server",method="GET",path="/api/v1/chats/{chat_id}/messages",status="200"} 3
status_bot_api_auth_failures_total{module="api_server"} 2
```

---

## Adding metrics to modules

The start_prometheus() function in status_bot/metrics.py automatically calls module.register_metrics() for each loaded module after setting up the built-in metrics.

`register_metrics()` is only called when `metrics.enabled` is `true`. Declare
your metric attributes as `None` on the module and guard every increment so the
module keeps working when the exporter is disabled — see how `api_server` does
it in `status_bot/modules/api_server.py`.

```python
from prometheus_client import Counter, Gauge
from status_bot.modules.base import BaseModule, ModuleType

class MyModule(BaseModule):

    @property
    def module_type(self) -> set[ModuleType]:
        return {ModuleType.PERIODIC}

    def register_metrics(self) -> None:
        # Register a counter with module name as label
        self._processed = Counter(
            "my_module_messages_processed_total",
            "Total messages processed by my module",
            ["module"]
        )
        # Store label-ref for incrementing
        self._counter = self._processed.labels(module=self.name)
        # You can also register gauges, histograms, etc.
        self._status = Gauge(
            "my_module_status",
            "Current status of my module",
            ["module"]
        )
        self._status.labels(module=self.name).set(0)

    def execute(self):
        # module logic...
        self._counter.inc() # increment after processing
        self._status.labels(module=self.name).set(1) # update gauge

```

## Example Prometheus scrape config

```yaml
scrape_configs:
  - job_name: "status-bot"
    static_configs:
      - targets: ["localhost:8000"]
```
