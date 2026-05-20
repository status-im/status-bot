# Configuration

The bot is configured through a YAML file (`config.yaml`) and environment variables.
Environment variables override values from the YAML file.

## Loading order

1. `config.yaml` — base configuration
2. Shell environment variables — override YAML values
3. `.env` file — override YAML values (loaded from the same directory as `config.yaml`)

## Usage

```bash
python main.py --config /path/to/config.yaml
```

The `--config` argument defaults to `./config.yaml`.

---

## Reference

### `sleep`

| Type | Default | Description |
|------|---------|-------------|
| `int` | `10` | Sleep interval in minutes between monitoring cycles |

### `files`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `current_state` | `str` | `"dates.pkl"` | File path for tracking latest message timestamps per chat |

```yaml
files:
    current_state: "dates.pkl"
```

---

### `bot`

| Field | Type | Default | Env var | Description |
|-------|------|---------|---------|-------------|
| `display_name` | `str` | `""` | `BOT_DISPLAY_NAME` | Status display name used to log in |
| `public_key` | `str` | `""` | — | Expected public key for verification |
| `password` | `str` | `""` | `BOT_PASSWORD` | Status account password |
| `mnemonic_phrase` | `str` | `""` | `BOT_MNEMONIC_PHRASE` | 12-word recovery phrase (used when `init_account: true`) |
| `init_account` | `bool` | `false` | `BOT_INIT_ACCOUNT` | If `false`, the account must already exist. If `true`, creates or restores the account using `mnemonic_phrase` |
| `compressed_key` | `str` | `""` | — | Expected compressed key for verification after login |
| `infura_token` | `str` | `""` | `BOT_INFURA_TOKEN` | [Infura token](https://www.infura.io/) required for token-gated communities |
| `coingecko_api_key` | `str` | `""` | `BOT_COINGECKO_API_KEY` | [CoinGecko API key](https://www.coingecko.com/) required for token-gated communities |


```yaml
bot:
    display_name: 'my-bot'
    public_key: '0x...'
    password: 'ChangeMe'
    mnemonic_phrase: 'word1 word2 ... word12'
    init_account: false
    compressed_key: 'zQ3...'
```

#### `bot.params`

Parameters passed to the `Account()` constructor.

| Field | Type | Default | Env var | Description |
|-------|------|---------|---------|-------------|
| `domain` | `str` | `"localhost"` | `BOT_PARAMS_DOMAIN` | Status Backend hostname (`localhost` for local, `status-backend` for Docker) |
| `port` | `int` | `8080` | `BOT_PARAMS_PORT` | Status Backend API port |
| `is_secure` | `bool` | `false` | `BOT_PARAMS_IS_SECURE` | Use HTTPS instead of HTTP |
```yaml
bot:
    params:
        domain: "status-backend"
        port: 8080
        is_secure: false
        infura_token: ""
        coingecko_api_key: ""
```

---

### `postgres`

| Field | Type | Default | Env var | Description |
|-------|------|---------|---------|-------------|
| `host` | `str` | `"database"` | `POSTGRES_HOST` | Postgres server hostname |
| `port` | `int` | `5432` | `POSTGRES_PORT` | Postgres server port |
| `user` | `str` | `""` | `POSTGRES_USER` | Postgres username |
| `password` | `str` | `""` | `POSTGRES_PASSWORD` | Postgres password |
| `name` | `str` | `""` | `POSTGRES_NAME` | Postgres database name |
| `schema` | `str` | `"public"` | `POSTGRES_SCHEMA` | Database schema for storing data |
| `tables` | `dict` | `{}` | — | Mapping of data type to table name |

```yaml
postgres:
    host: database
    port: 5432
    user: 'myuser'
    password: 'ChangeMe'
    name: 'status-bot'
    schema: "status_app_monitoring"
    tables:
        messages: "raw_messages"
        community: "raw_community_info"
```

---

### `modules`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `directories` | `list[str]` | `["./modules"]` | Directories to scan for module `.py` files |
| `enabled` | `list[str]` | `[]` | List of module names to enable |
| `settings` | `dict` | `{}` | Per-module settings (each module defines its own schema) |

```yaml
modules:
    directories:
        - ./modules
    enabled:
        - monitoring
    settings:
        monitoring:
            interval: 600
            max_retries: 3
            backoff_seconds: 30
```

---

### `prometheus`

| Field | Type | Default | Env var | Description |
|-------|------|---------|---------|-------------|
| `enabled` | `bool` | `false` | `PROMETHEUS_ENABLED` | Enable Prometheus metrics HTTP server |
| `host` | `str` | `"0.0.0.0"` | `PROMETHEUS_HOST` | Prometheus HTTP server bind address |
| `port` | `int` | `8000` | `PROMETHEUS_PORT` | Prometheus HTTP server port |

```yaml
prometheus:
    enabled: true
    host: "0.0.0.0"
    port: 8000
```

---

## Environment variables

All configuration fields can be set via environment variables using the `_` separator for nested fields.

| Env var | Config path |
|---------|-------------|
| `BOT_DISPLAY_NAME` | `bot.display_name` |
| `BOT_PASSWORD` | `bot.password` |
| `BOT_MNEMONIC_PHRASE` | `bot.mnemonic_phrase` |
| `BOT_INIT_ACCOUNT` | `bot.init_account` |
| `BOT_PARAMS_DOMAIN` | `bot.params.domain` |
| `BOT_PARAMS_PORT` | `bot.params.port` |
| `BOT_PARAMS_IS_SECURE` | `bot.params.is_secure` |
| `BOT_PARAMS_INFURA_TOKEN` | `bot.params.infura_token` |
| `BOT_PARAMS_COINGECKO_API_KEY` | `bot.params.coingecko_api_key` |
| `POSTGRES_HOST` | `postgres.host` |
| `POSTGRES_PORT` | `postgres.port` |
| `POSTGRES_USER` | `postgres.user` |
| `POSTGRES_PASSWORD` | `postgres.password` |
| `POSTGRES_NAME` | `postgres.name` |
| `POSTGRES_SCHEMA` | `postgres.schema` |
| `PROMETHEUS_ENABLED` | `prometheus.enabled` |
| `PROMETHEUS_HOST` | `prometheus.host` |
| `PROMETHEUS_PORT` | `prometheus.port` |

Example `.env` file:

```
# Bot account
BOT_DISPLAY_NAME=my-bot
BOT_PASSWORD=ChangeThisPassword
BOT_MNEMONIC_PHRASE=test test test test test test test test test test test test

# Postgres
POSTGRES_HOST=database
POSTGRES_PORT=5432
POSTGRES_NAME=status-bot
POSTGRES_USER=status
POSTGRES_PASSWORD=ChangeThisOneAlso
```
