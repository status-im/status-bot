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

## Available metrics

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

## Example Prometheus scrape config

```yaml
scrape_configs:
  - job_name: "status-bot"
    static_configs:
      - targets: ["localhost:8000"]
```
