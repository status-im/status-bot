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
* Applied `ruff` formatting across the codebase
* New exception types in `status_bot/exceptions.py`
* Documentation updated (`docs/deployment/metrics.md`, `docs/development/modules.md`)

## Bug fix

* Fixed `run_event` in module manager
* Fixed SQLAlchemy version pinning
* Fixed hardcoded version in `status_bot_version` metric (now dynamically reads from `pyproject.toml` via `importlib.metadata`)

## Documentation

* Fixed missing metrics in `docs/deployment/metrics.md` (execution time histograms, community monitoring, engagement metrics)
* Fixed `BaseModule` API docs in `docs/development/modules.md` (missing base class, wrong `on_event` signature, typo in `_mandatory_properties`)
* Fixed missing bot config fields in `docs/deployment/configuration.md` (`chat_key`, `bio`, `profil_picture_path`, `alchemy_token`)
* Fixed wrong module name in `docs/usage/monitoring.md` (`communities_monitoring` → `community_monitoring`)
* Fixed database `schema` → `schema_name` in configuration example
* Fixed bot config example in `docs/index.md`

## Tests

* Added `tests/test_api_metrics.py` for API metrics coverage
