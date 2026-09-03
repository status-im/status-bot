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

### `status_bot_module_errors_total`

| Type | Labels | Description |
|------|--------|-------------|
| Counter | `module` | Total number of errors encountered by a module |

### `status_bot_module_restarts_total`

| Type | Labels | Description |
|------|--------|-------------|
| Counter | `module` | Total number of times a module has been restarted |

---

## Adding metrics to modules

The start_prometheus() function in status_bot/metrics.py automatically calls module.register_metrics() for each loaded module after setting up the built-in metrics.

```python
from prometheus_client import Counter, Gauge
from status_bot.modules.base import BaseModule, ModuleType

class MyModule(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.PERIODIC

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
