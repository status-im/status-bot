# AGENTS.md

Guidance for LLM agents (or humans) working in this repository. This file documents
the repository's actual behavior, so trust it over stale prose in `README.md` or
`docs/` when they disagree.

## Project overview

A Python bot for the [Status App](https://status.app), built on the
[`status-sdk`](https://github.com/status-im/status-python-sdk). The bot automates
tasks, monitors communities, responds to commands, and integrates with external
APIs. Entry point is `main.py`.

The recommended deployment is with docker compose, which runs three containers:

- **Status backend** (status-go) — the delivery node the bot talks to.
- **Status bot** — this codebase, as a container.
- **Postgres database** — optional persistence.

The bot's behavior is extended through **modules**, which run as daemon threads.
A `ModuleManager` (`status_bot/modules/manager.py`) discovers, loads, restarts
(with exponential backoff), and stops modules. See `docs/development/modules.md`
for the module API (`BaseModule`, `ModuleType`, `ModuleContext`).

## Repository map

- `main.py` — CLI entry point. Parses `--config`, loads `Config`, sets up logging,
  creates/stores the bot account (`create_bot`), initializes the database, and
  starts the module manager. Also exposed as the `status-bot` console script
  (`pyproject.toml` → `[project.scripts]`).
- `status_bot/config.py` — all pydantic configuration models.
- `status_bot/logger.py` — centralized logging setup, formatters, and secret redaction.
- `status_bot/database.py` — `Database` wrapper (Postgres / SQLite) around SQLAlchemy; exposes `create_tables()`.
- `status_bot/models/base.py` — Declarative `Base`, plus `namespace()` and `model_by_table()` helpers (re-exported from the top-level `status_bot` package).
- `status_bot/metrics.py` — Prometheus metrics exporter startup.
- `status_bot/models/` — SQLAlchemy ORM models (`ReceivedMessage`, `ReceivedChat`).
- `status_bot/modules/` — built-in modules and the module framework.
- `tests/` — pytest test suite.
- `docs/` — user and development documentation.
- `config.yaml` — default runtime configuration.
- `pyproject.toml`, `Dockerfile`, `docker-compose.yaml`, `Jenkinsfile`.

## Run & test commands

```bash
pip install -e '.[dev]'      # install the package with dev dependencies
pytest tests/                # run the test suite (from the project root)
python main.py --config config.yaml   # run the bot
```

The full stack is available via docker compose (`docker-compose.yaml`).

## Development rules

These rules are mandatory for any new development in this repository.

### Configuration

- Global/runtime configuration is declared as pydantic models in
  `status_bot/config.py` (`Config`, `BotConfig`, `BackendConfig`, `DatabaseConfig`,
  `ApiConfig`, `MetricsConfig`, `ModulesConfig`, `LoggingConfig`). New global
  settings are added as typed fields on the appropriate model there.
- Environment variables override YAML values and follow the naming rule
  `SECTION__FIELD` (uppercase, joined with a double underscore via the nested
  delimiter), e.g. `LOGGING__LEVEL`, `BOT__PASSWORD`. See
  `docs/deployment/configuration.md` for the full reference.
- Module-specific settings live under `modules.settings.<module_name>` in
  `config.yaml` and are read via `self.ctx.config.settings`. Each module owns its
  own settings namespace.

### Logging

- Use the stdlib `logging` library. Each module/component defines
  `logger = logging.getLogger(__name__)` and logs through it.
- Global logging setup (format, level, secret redaction) is centralized in
  `status_bot/logger.py` via `setup_logging(config)`. Call it with the loaded
  `Config` so the `RedactFilter` masks configured secrets in log output.
- Do not use `print()` or ad-hoc stdout for logging.

### Testing

- All new development must be covered by tests.
- Tests live in `tests/` (pytest), runnable with `pytest tests/`.
- Prefer testing pure logic — e.g. the hashing/transform functions in
  `status_bot/modules/receiver.py` (see `tests/test_receiver.py`), or database
  inserts against an in-memory SQLite database (see `tests/test_database.py`) —
  rather than exercising the live Status backend.

## Documentation

The documentations is split between multiple subdirectories:
* **deployment**: contains the information for the setup and the usage of the Bot.
* **development**: contains all the documentation for developing new fonctionnality
* **usage**: contains explaination on how to use the bot.

## Key configuration facts

- Loading order: `config.yaml` → environment variables → `.env` file.
- `Config._yaml_file` defaults to `./config.yaml` and is set from the `--config`
  CLI flag before the `Config` instance is created.
- Database is optional: if the required `database` settings are absent, the bot
  runs without persistence.
- Secrets (bot password, mnemonic phrase, API keys, database password, hash
  pepper) are redacted as `[REDACTED]` from logs when `setup_logging(config)` is
  called with the loaded configuration.
