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

> **Security**: secret values (`bot.password`, `bot.mnemonic_phrase`, `bot.infura_token`, `bot.coingecko_api_key`, `bot.bot_hash_pepper`, `bot.encryption_key`, `api.api_key`, `database.password`) are masked as `[REDACTED]` in any log line, wherever they appear.

---

## Reference

### `bot`

| Field | Type | Default | Env var | Description |
|-------|------|---------|---------|-------------|
| `name` | `str` | `""` | `BOT__NAME` | Status display name used to log in |
| `chat_key` | `str` | `""` | `BOT__CHAT_KEY` | Chat key for the account |
| `bio` | `str` | `"Just a bot"` | `BOT__BIO` | Profile bio text |
| `profil_picture_path` | `str` | `"assets/profile.jpg"` | `BOT__PROFIL_PICTURE_PATH` | Path to profile picture |
| `password` | `str` | `""` | `BOT__PASSWORD` | Status account password |
| `mnemonic_phrase` | `str` | `null` | `BOT__MNEMONIC_PHRASE` | 12-word recovery phrase (used to create/restore account) |
| `infura_token` | `str` | `null` | `BOT__INFURA_TOKEN` | [Infura token](https://www.infura.io/) required for token-gated communities |
| `alchemy_token` | `str` | `null` | `BOT__ALCHEMY_TOKEN` | [Alchemy token](https://www.alchemy.com/) for EVM access |
| `coingecko_api_key` | `str` | `""` | `BOT__COINGECKO_API_KEY` | [CoinGecko API key](https://www.coingecko.com/) required for token-gated communities |
| `bot_hash_pepper` | `str` | `""` | `BOT__BOT_HASH_PEPPER` | Secret key used for HMAC-SHA256 hashing of stored data (see [Privacy & storage](#privacy--storage)) |
| `encryption_key` | `str` | `""` | `BOT__ENCRYPTION_KEY` | Secret used to encrypt stored messages (AES-256-SIV, see [Privacy & storage](#privacy--storage)) |


```yaml
bot:
    name: 'my-bot'
    chat_key: 'zQ3...'
    bio: 'Just a bot'
    profil_picture_path: 'assets/profile.jpg'
    password: 'ChangeMe'
    mnemonic_phrase: 'word1 word2 ... word12'
    infura_token: 'your-infura-token'
    alchemy_token: 'your-alchemy-token'
    coingecko_api_key: 'your-coingecko-key'
    bot_hash_pepper: 'your-secret-pepper'
    encryption_key: 'your-secret-encryption-key'
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
| `schema_name` | `str` | `"public"` | `DATABASE__SCHEMA_NAME` | Database schema (Postgres) |

Postgres example:
```yaml
database:
    type: postgres
    host: database
    port: 5432
    user: 'myuser'
    password: 'ChangeMe'
    name: 'status-bot'
    schema_name: "status_app_monitoring"
```

SQLite example:
```yaml
database:
    type: sqlite
    name: "/data/status-bot.db"
```

---

## Privacy & storage

The `receiver` module encrypts identifying and content-bearing fields before persisting messages, so no human-readable user data is stored at rest.

| Field | Env var | Description |
|-------|---------|-------------|
| `bot.encryption_key` | `BOT__ENCRYPTION_KEY` | Secret used to derive the AES-256-SIV key that encrypts stored messages. Must be stable across restarts (changing it makes previously stored rows unreadable). Accepts a hex/base64 encoded 32/48/64 byte key directly, or any passphrase (stretched with PBKDF2-HMAC-SHA256). If unset, the bot logs a warning and derives the key from an empty secret — stored messages are then only obfuscated |

**Encryption scheme:**

- **Deterministic (AES-256-SIV, no nonce):** all identifying, correlation, and content fields, so `id` stays stable for primary-key dedup. Encrypted values are stored with an `enc1$` prefix (base64 of synthetic IV + ciphertext).

| Entity | Columns |
|--------|---------|
| Messages | `id`, `from`, `response_to`, `chat_id`, `text` |

Messages arrive as `status_sdk` `Message` objects: `content_type` is stored as its integer value (`Content` enum unwrapped), `chat_type` as the enum member name (`PRIVATE`/`GROUP`/`COMMUNITY`) in `message_type`, and `whisper_timestamp`/`received_timestamp` as datetimes.

Event payloads are kept in plaintext in-memory so they can be handled correctly; only the persisted copy is encrypted.

**Upgrading from the previous HMAC-SHA256 scheme:** rows written by older versions are HMAC digests and can never be decrypted. Purge them once, before restarting the bot with the new version:

```sql
DELETE FROM received_messages;  -- legacy rows are not decryptable
-- optional, the receiver no longer writes chats:
DELETE FROM received_chats;
```

Rows that were not purged can be spotted with `SELECT ... WHERE id NOT LIKE 'enc1$%'`.

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
