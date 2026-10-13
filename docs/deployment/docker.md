# Docker deployment

The recommended way to run the bot is with docker compose (`docker-compose.yaml` in the repository root). It spins up three containers on a shared `status-bridge` network:

| Service | Image / build | Role |
|---------|---------------|------|
| `backend` | `harbor.status.im/status-im/status-go:status-bot-1.0.0` | Status Backend (status-go) — the delivery node the bot talks to on the Status network |
| `bot` | built from the repo `Dockerfile` (`python:3.12-slim`, `pip install -e .`, `python main.py`) | The Status Bot itself |
| `database` | `postgres:15` | Postgres database for message storage and analytics |

## Ports

| Host port | Container | Service | Purpose |
|-----------|-----------|---------|---------|
| `8080` | `8080` | `backend` | Status Backend HTTP API |
| `9001`, `9002` | `9000`, `9001` | `backend` | Media server (images, profile pictures) |
| `8545`, `30303` | `8545`, `30303` | `backend` | EVM RPC / p2p |
| `8081` | `8081` | `bot` | REST API (see [Messaging API](../usage/messaging.md)) |
| `8000` | `8000` | `bot` | Prometheus metrics (see [Metrics](./metrics.md)) |
| `5432` | `5432` | `database` | Postgres |

## Quick start

```bash
cp .env.example .env   # fill in the secrets
mkdir -p config && cp config.yaml config/config.yaml
docker compose up -d --build
```

## Configuration

- The bot container mounts `./config/config.yaml` as its configuration file — edit that copy (or the repo `config.yaml` before copying) to change settings. See [Configuration](./configuration.md) for all options.
- The bot container loads `./.env` via `env_file` — environment variables there override `config.yaml` values (see [Loading order](./configuration.md#loading-order)).
- The `database` service is created with `POSTGRES_DB=status-bot`, `POSTGRES_USER=status`, `POSTGRES_PASSWORD=ChangeMeIfYouCare` — either keep the matching values in your bot configuration or override them with `DATABASE__*` environment variables.

## Volumes

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `./backups` | `/backups` (bot), `/root/.config/Status/backups` (backend) | Status account backups (`.bkp`) for restoring an existing account |
| `./assets` / `/assets` | `/assets` | Images and profile pictures shared with the backend |
| `./backend-data` | `/data` | status-go node data (persisted across restarts) |
| `postgres-data` (named volume) | `/var/lib/postgresql` | Postgres data (persisted across restarts) |

## Health & logs

```bash
docker compose ps                 # container status (backend and database have healthchecks)
docker compose logs -f bot        # follow the bot logs
docker compose logs -f backend    # follow the status-go logs
```
