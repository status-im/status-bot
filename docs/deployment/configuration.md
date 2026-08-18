# Configuration

The bot is configured through a YAML file (`config.yaml`), environment variables, and an optional `.env` file.

## Loading order

Sources are resolved in priority order (highest first). A value is taken from the first source that defines it; later sources only fill in settings not set by a higher-priority source:

1. `config.yaml` — highest priority; overrides environment variables and the `.env` file
2. Shell environment variables — override the `.env` file
3. `.env` file — lowest priority, used as fallback (loaded from the current working directory)

## Usage

```bash
python main.py --config /path/to/config.yaml
```

The `--config` argument defaults to `./config.yaml`.

---

## Logging

The bot logs to **stdout/stderr**. Human-readable lines are the default; JSON output can be enabled for log aggregators.

| Field | Type | Default | Env var | Description |
|-------|------|---------|---------|-------------|
| `format` | `human` \| `json` | `"human"` | `LOGGING__FORMAT` | Output format. `human` prints `time | LEVEL | thread | logger | message`; `json` emits one flat JSON object per line (`timestamp`, `level`, `logger`, `thread`, `message`, `exception`) |
| `level` | `debug` \| `info` \| `warning` \| `error` | `"info"` | `LOGGING__LEVEL` | Minimum severity logged. Applies to the root logger; noisy libraries (`sqlalchemy`, `urllib3`, `websockets`) are always quieted to `warning` |
| `uvicorn_access` | `bool` | `false` | `LOGGING__UVICORN_ACCESS` | When `true`, the FastAPI/uvicorn per-request access logs are enabled (they inherit the chosen `format`) |

```yaml
logging:
    format: human   # or json
    level: info
    uvicorn_access: false
```

> **Security**: secret values (`bot.password`, `bot.mnemonic_phrase`, `bot.infura_token`, `bot.coingecko_api_key`, `bot.bot_hash_pepper`, `api.api_key`, `database.password`) are masked as `[REDACTED]` in any log line, wherever they appear.

---

## Reference

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
| `name` | `str` | `""` | `BOT__NAME` | Status display name used to log in |
| `public_key` | `str` | `""` | `BOT__PUBLIC_KEY` | Expected public key for verification |
| `password` | `str` | `""` | `BOT__PASSWORD` | Status account password |
| `mnemonic_phrase` | `str` | `""` | `BOT__MNEMONIC_PHRASE` | 12-word recovery phrase (used when `init_account: true`) |
| `init_account` | `bool` | `false` | `BOT__INIT_ACCOUNT` | If `false`, the account must already exist. If `true`, creates or restores the account using `mnemonic_phrase` |
| `compressed_key` | `str` | `""` | `BOT__COMPRESSED_KEY` | Expected compressed key for verification after login |
| `infura_token` | `str` | `""` | `BOT__INFURA_TOKEN` | [Infura token](https://www.infura.io/) required for token-gated communities |
| `coingecko_api_key` | `str` | `""` | `BOT__COINGECKO_API_KEY` | [CoinGecko API key](https://www.coingecko.com/) required for token-gated communities |
| `bot_hash_pepper` | `str` | `""` | `BOT__BOT_HASH_PEPPER` | Secret key used for HMAC-SHA256 hashing of stored messages (see [Privacy & storage](#privacy--storage)) |


```yaml
bot:
    name: 'my-bot'
    public_key: '0x...'
    password: 'ChangeMe'
    mnemonic_phrase: 'word1 word2 ... word12'
    init_account: false
    compressed_key: 'zQ3...'
```

### `backend`

Parameter to connect to the Status Backend instance.

| Field | Type | Default | Env var | Description |
|-------|------|---------|---------|-------------|
| `domain` | `str` | `"localhost"` | `BACKEND__DOMAIN` | Status Backend hostname (`localhost` for local, `status-backend` for Docker) |
| `backend_port` | `int` | `8080` | `BACKEND__BACKEND_PORT` | Status Backend API port |
| `is_secure` | `bool` | `false` | `BACKEND__IS_SECURE` | Use HTTPS instead of HTTP |
```yaml
backend:
    domain: "status-backend"
    backend_port: 8080
    is_secure: false
```

---

### `api`

Configuration for the WebServer avaialable to the modules.

| Field | Type | Default | Env var | Description |
|-------|------|---------|---------|-------------|
| `enable` | `bool` | `true` | `API__ENABLE` | Enable the REST API server |
| `host` | `str` | `"0.0.0.0"` | `API__HOST` | API server bind address |
| `port` | `int` | `8081` | `API__PORT` | API server port |
| `api_key` | `str` | `""` | `API__API_KEY` | API key for request authentication (empty = disabled) |

```yaml
api:
    enable: true
    host: "0.0.0.0"
    port: 8081
    # api_key: "your-secret-key"
```

---

### `database`

Supports **Postgres** and **SQLite** (SQLite via `type: sqlite`, where `name` is the file path).

| Field | Type | Default | Env var | Description |
|-------|------|---------|---------|-------------|
| `type` | `str` | `"postgres"` | `DATABASE__TYPE` | Database engine (`postgres` or `sqlite`) |
| `host` | `str` | `"database"` | `DATABASE__HOST` | Database server hostname (Postgres) |
| `port` | `int` | `5432` | `DATABASE__PORT` | Database server port (Postgres) |
| `user` | `str` | `""` | `DATABASE__USER` | Database username (Postgres) |
| `password` | `str` | `""` | `DATABASE__PASSWORD` | Database password (Postgres) |
| `name` | `str` | `""` | `DATABASE__NAME` | Database name (Postgres) or file path (SQLite) |
| `schema` | `str` | `"public"` | `DATABASE__SCHEMA` | Database schema (Postgres) |
| `tables` | `dict` | `{}` | — | Mapping of data type to table name |

Postgres example:
```yaml
database:
    type: postgres
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

SQLite example:
```yaml
database:
    type: sqlite
    name: "/data/status-bot.db"
```

---

## Privacy & storage

The `receiver` module hashes identifying and content-bearing fields before persisting messages and chats, so no human-readable user data is stored at rest.

| Field | Env var | Description |
|-------|---------|-------------|
| `bot.bot_hash_pepper` | `BOT__BOT_HASH_PEPPER` | Secret key used for HMAC-SHA256 hashing. Must be stable across restarts (changing it breaks dedup and changes all stored hashes). If unset, the bot logs a warning and falls back to plain SHA-256 — content is then not protected against dictionary attacks |

**Hashing scheme:**

- **Deterministic (HMAC, pepper only):** all identifying, correlation, and content fields, so `id` stays stable for dedup.

| Entity | Columns |
|--------|---------|
| Messages | `id`, `from`, `response_to`, `chat_id`, `local_chat_id`, `text`, `display_name`, `ens_name`, `alias` |
| Chats | `id`, `name` |

**Dropped entirely (messages):** `parsed_text`, `quoted_message`, `emoji_hash`, `gap_parameters`. Any other structured (dict/list) column is dropped with a logged warning.

Event payloads are kept in plaintext in-memory so they can be handled correctly; only the persisted copy is hashed. Rows stored before this behavior was introduced are not backfilled.

---

### `modules`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `directories` | `list[str]` | `["./modules", "bot/modules"]` | Directories to scan for module `.py` files |
| `enabled` | `list[str]` | `[]` | List of module names to enable |
| `settings` | `dict` | `{}` | Per-module settings (each module defines its own schema) |

The `api_server` module is auto-loaded whenever `api.enable` is `true` — it does not need to be listed in `enabled`.

```yaml
modules:
    directories:
        - ./modules
    enabled:
        - messaging
    settings:
        messaging: {}
```

---

### `metrics`

| Field | Type | Default | Env var | Description |
|-------|------|---------|---------|-------------|
| `enabled` | `bool` | `false` | `METRICS__ENABLED` | Enable Prometheus metrics HTTP server |
| `host` | `str` | `"0.0.0.0"` | `METRICS__HOST` | Prometheus HTTP server bind address |
| `port` | `int` | `8000` | `METRICS__PORT` | Prometheus HTTP server port |

```yaml
metrics:
    enabled: true
    host: "0.0.0.0"
    port: 8000
```
