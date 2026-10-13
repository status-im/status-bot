# Changelog - v1.1.0

## New feature

* **Prometheus metrics** - Comprehensive metrics instrumentation across the bot:
    * Module execution time tracking
    * Module start/failure counters
    * Periodic execution counters
    * Metrics for `community_monitoring` module
* **API metrics** - New `api_server` module with API endpoint metrics
* **Mandatory config validation** - `BaseModule` verifies required properties at startup via `_verify_mandatory_config()`

## Changes

* `BaseModule` - Refactored module startup:
    * New `on_start()` lifecycle hook that calls `start()` and `_verify_mandatory_config()`
    * `_verify_mandatory_config()` uses the `_mandatory_properties` property
* Metrics added to `community_monitoring`, `manager`, and `messaging` modules
* New exception types in `status_bot/exceptions.py`
* `receiver` Module - Messages are encrypted (AES-256-SIV) instead of HMAC-SHA256 hashed; new `bot.encryption_key` config field (redacted from logs); the module no longer persists chats (events only carry messages)
* Removed dead code: `to_hmac_sha256_hash()` and the `bot.bot_hash_pepper` config field (unused since stored messages moved to encryption), the `namespace()` / `model_by_table()` helpers in `status_bot/models/base.py`, and the `ReceivedChat` model (the `received_chats` table is no longer created)

## Bug fix

* Fixed SQLAlchemy version pinning
* Fixed hardcoded version in `status_bot_version` metric (now dynamically reads from `pyproject.toml` via `importlib.metadata`)

## Upgrade notes

* **Purge legacy message rows.** Rows written by previous versions are HMAC-SHA256 digests and can never be decrypted. Before restarting with this version, run:

  ```sql
  DELETE FROM received_messages;
  -- the ReceivedChat model was removed; drop the orphaned table
  DROP TABLE IF EXISTS received_chats;
  ```

* Set `bot.encryption_key` (or `BOT__ENCRYPTION_KEY`) to a large random value. It must stay stable across restarts — changing it makes previously stored rows unreadable. If unset, the bot logs a warning and derives the key from an empty secret (stored messages are then only obfuscated).
* `bot.bot_hash_pepper` / `to_hmac_sha256_hash()` were removed. Configs still setting `bot_hash_pepper` keep loading fine (the field is ignored).
