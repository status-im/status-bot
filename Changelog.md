# Changelog - v1.1.0

## New feature

* **Prometheus metrics** - Comprehensive metrics instrumentation across the bot:
    * Module execution time tracking
    * Module start/failure counters
    * Periodic execution counters
    * Metrics for `community_monitoring` module
* **API metrics** - New `api_server` module with API endpoint metrics
* **Mandatory config validation** - `BaseModule` verifies required properties at startup via `_verify_mandatory_config()`
* **Message storage in `receiver`** - The module now persists every received `status_sdk` `Message` into `received_messages`. The message content (`text`) and the identifying fields (`id`, `from`, `response_to`, `chat_id`) are encrypted with AES-256-SIV (deterministic, so primary-key dedup keeps working) using the new `bot.encryption_key` setting (`BOT__ENCRYPTION_KEY`). `content_type` is stored as its integer value and `message_type` as the chat type name (`PRIVATE`/`GROUP`/`COMMUNITY`)

## Changes

* `BaseModule` - Refactored module startup:
    * New `on_start()` lifecycle hook that calls `start()` and `_verify_mandatory_config()`
    * `_verify_mandatory_config()` uses the `_mandatory_properties` property
* Metrics added to `community_monitoring`, `manager`, and `messaging` modules
* Applied `ruff` formatting across the codebase
* New exception types in `status_bot/exceptions.py`
* Documentation updated (`docs/deployment/metrics.md`, `docs/development/modules.md`)
* `receiver` - Messages are encrypted (AES-256-SIV) instead of HMAC-SHA256 hashed; new `bot.encryption_key` config field (redacted from logs); the module no longer persists chats (events only carry messages)
* `pycryptodome` added as an explicit dependency (used for AES-SIV)

## Bug fix

* Fixed `run_event` in module manager
* Fixed SQLAlchemy version pinning
* Fixed hardcoded version in `status_bot_version` metric (now dynamically reads from `pyproject.toml` via `importlib.metadata`)
* Fixed `receiver` module: `on_event()` was a stub and `_process_and_insert()` referenced an undefined variable, so received messages were never stored
* Fixed stale tests referencing `ReceivedMessage` columns removed earlier (`seen`, `rtl`, `line_count`, `local_chat_id`, `clock`, `replace`, `ens_name`, `display_name`, `timestamp`)

## Upgrade notes

* **Purge legacy message rows.** Rows written by previous versions are HMAC-SHA256 digests and can never be decrypted. Before restarting with this version, run:

  ```sql
  DELETE FROM received_messages;
  -- optional: the receiver no longer writes chats
  DELETE FROM received_chats;
  ```

* Set `bot.encryption_key` (or `BOT__ENCRYPTION_KEY`) to a large random value. It must stay stable across restarts — changing it makes previously stored rows unreadable. If unset, the bot logs a warning and derives the key from an empty secret (stored messages are then only obfuscated).

## Documentation

* Fixed missing metrics in `docs/deployment/metrics.md` (execution time histograms, community monitoring, engagement metrics)
* Fixed `BaseModule` API docs in `docs/development/modules.md` (missing base class, wrong `on_event` signature, typo in `_mandatory_properties`)
* Fixed missing bot config fields in `docs/deployment/configuration.md` (`chat_key`, `bio`, `profil_picture_path`, `alchemy_token`)
* Fixed wrong module name in `docs/usage/monitoring.md` (`communities_monitoring` → `community_monitoring`)
* Fixed database `schema` → `schema_name` in configuration example
* Fixed bot config example in `docs/index.md`

## Tests

* Added `tests/test_api_metrics.py` for API metrics coverage
