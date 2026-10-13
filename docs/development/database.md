# Database Layer Architecture

## Overview

The bot persists data through a small **ORM-only** database layer built on SQLAlchemy, backed by Postgres in production and SQLite for tests and demos. The layer exists to give every module a simple, safe way to persist its state without touching core code: modules define SQLAlchemy models that are discovered automatically, and their tables are created in a **single `create_all` pass once every module is loaded**.

The layer makes three deliberate trade-offs:

- **ORM-first, always.** No dataframes, no raw-dict bulk inserts, no SQL string building in modules. All persistence goes through ORM models and sessions.
- **One shared metadata.** Every model — core and module-defined alike — lives on the same declarative `Base.metadata`, so one `create_all` covers the whole schema.
- **`create_all` as the MVP schema strategy.** Tables are created (not migrated); schema evolution is out of scope for now (see *Future work*).

## Components

| Component | Where | Role |
|---|---|---|
| `Database` | `status_bot/database.py` | Wraps the engine and session factory. Surface: `session()`, `create_tables(tables=None)`. Supports `postgres` and `sqlite` URL schemes. |
| `Base` | `status_bot/models/base.py` | SQLAlchemy `DeclarativeBase`. The single registry every model registers on. |
| Core models | `status_bot/models/` | `ReceivedMessage`, `RawCommunityInfo`, `RawMessage`, `ContactRequest`, `FeedbackMessage`. |
| `ModuleContext.db` | `status_bot/modules/base.py` | How a module receives the shared `Database` instance — or `None` when no database is configured. |

Both `Base` and `Database` are re-exported from the top-level `status_bot` package for a single import point.

## Startup flow (two-phase table initialization)

Tables must be created *after* module models exist. The flow in `main.py` is therefore:

```mermaid
flowchart TD
    A[Load config / config.yaml + env] --> B[create_bot]
    B --> C[init_database: build Database, no tables yet]
    C --> D[discover_modules]
    D --> E[load_modules]
    E --> F[db.create_tables - one create_all for all models]
    F --> G[start_prometheus]
    G --> H[start_all: one daemon thread per module]
    F --> I[(Postgres / SQLite)]
```

```text
1. init_database()   # engine + session factory, tables NOT created yet
2. discover_modules()# importing module files registers their models on Base.metadata
3. load_modules()    # instantiate modules (each receives ModuleContext.db)
4. db.create_tables()# create_all now covers core + module tables
5. start_all()       # modules run as daemon threads
```

This is what makes the design work: a model defined at module level in any module file is simply present on `Base.metadata` by the time `create_tables()` runs. No core edits are needed to add a table.

## Defining module models

Modules declare their tables with a model on the shared `Base`. Pick a `__tablename__` prefix that cannot collide with the core tables (`received_messages`, `raw_community_infos`, `raw_messages`, `contact_requests`, `feedback_messages`) or with other modules:

```python
from status_bot import Base
from sqlalchemy import Column, Integer, String


class Visit(Base):
    __tablename__ = "mymodule_visit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String, nullable=False)
```

Because a module file is imported during `discover_modules()`, module-level model definitions are registered on `Base.metadata` automatically and picked up by the single `create_all` in `create_tables()`.

## Writing and reading data

`Database` never exchanges dataframes — modules build ORM objects and commit through short-lived sessions:

```python
with self.ctx.db.session() as session:
    session.add_all(rows)
    session.commit()

with self.ctx.db.session() as session:
    rows = session.execute(select(Visit)).scalars().all()
```

Built-in modules follow the same contract: `receiver` converts each received `status_sdk` `Message` into a `ReceivedMessage` row (encrypting identifying and content-bearing columns) and commits it; `communities_monitoring` uses `session.merge()` for primary-key upserts. Since `self.ctx.db` may be `None`, modules always guard before touching the database.

## Thread model

Each module runs in its own daemon thread via the `ModuleManager`. The layer provides a session factory but no shared session, which is deliberate: SQLAlchemy sessions are not thread-safe, so modules are expected to open a fresh session per operation, and never share one across threads. The single shared object is the engine, which is thread-safe.

## Future work

- **Versioned migrations (Alembic).** `create_all` handles green-field schema only. Once the schema is established in production, adding/altering columns needs real migrations.
