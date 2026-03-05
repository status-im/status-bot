# [Status App Monitoring](https://status.app/)

Monitoring tool for Status App communities

# Setup

## Environment Variables

- `POSTGRES_USERNAME` - Postgres username.
- `POSTGRES_DATABASE` - The database name in the Postgres connection.
- `POSTGRES_HOST` - The Postgres host name that will be remotely connected to.
- `POSTGRES_PORT` - The Postgres port that will be remotely connected to.
- `STATUS_BACKEND_BASE_URL` (**OPTIONAL**) - The Status Backend URL. If you are running locally you do not need this variable (`localhost` will be automatically set). If you are running it in a Docker container, please set it to `status-backend` (as the `container_name` of the `docker-compose.yaml`).


## Docker

1. Login to `harbor.status.im`. Your password is your Harbor **CLI secret**.

```bash
docker login harbor.status.im
```

2. Run `docker-compose.yaml` file

```bash
docker compose up
```
**Note**: If you want to run Status Backend only, just keep the `status-backend` key in [`services`](./docker-compose.yaml).

## Python
1. Setup environment
```bash
conda create -n status-monitoring python=3.12
```

2. Install requirements

```bash
pip install -r requirements.txt
```

**Note**: If you are on Windows, you will have to install `psycopg2` instead of `psycopg2-binary`.

## Files

- `create_account.py` - create a Status App account for the given `username` and `password`. Example runs:
  - `python create_account.py -u snt-maxxer -p StatusApp#123`
  - `python create_account.py --username snt-maxxer --password StatusApp#123`
- `download.py` - download all messages and overall community info from the specified Status App channels in `config.yaml`.
- `upload.py` - upload data from `download.py` to Postgres
