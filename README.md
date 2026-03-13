# [Status App Monitoring](https://status.app/)

Monitoring tool for Status App communities

# Setup

## Environment Variables

- `POSTGRES_USERNAME` - Postgres username.
- `POSTGRES_PASSWORD` - Postgres password.
- `POSTGRES_DATABASE` - The database name in the Postgres connection.
- `POSTGRES_HOST` - The Postgres host name that will be remotely connected to.
- `POSTGRES_PORT` - The Postgres port that will be remotely connected to.
- `STATUS_BACKEND_BASE_URL` (**OPTIONAL**) - The Status Backend URL. If you are running locally you do not need this variable (`localhost` will be automatically set). If you are running it in a Docker container, please set it to `status-backend` (as the `container_name` of the `docker-compose.yaml`).
- `STATUS_USERNAME` - The Status username that will be used to create an account. This is required if you are running **Dockerfile** for `create_account.py`.
- `STATUS_PASSWORD` - The Status password that will be used to create an account. This is required if you are running **Dockerfile** for `create_account.py`.

## Docker deployement

You can use the `docker-compose.yaml` to run the project.

Example of `.env` file to use
```
# Status Backend connection
STATUS_BACKEND_BASE_URL=status-backend
STATUS_USERNAME=bot-status
STATUS_PASSWORD=ChangeThisPassword
INIT_ACCOUNT=true
# Database config
POSTGRES_HOST=database
POSTGRES_PORT=5432
POSTGRES_DATABASE=status-bot
POSTGRES_USERNAME=status
POSTGRES_PASSWORD=ChangeThisOneAlso
```

` INIT_ACCOUNT=true` will create a new account, if set to false, it will the credentials in the `accounts/ ` directory.

### Status Backend

Run Backend independently so you can develop and test locally.

```bash
docker compose run status-backend up -d
```

## Python

1. Setup environment. [Conda](https://www.anaconda.com/) example:
```bash
conda create -n status-monitoring python=3.12
```

**Note**: Code has been tested with **Python 3.12**.

2. Install requirements

```bash
pip install -r requirements.txt
```

**Note**: If you are on Windows, you will have to install `psycopg2` instead of `psycopg2-binary`.

# Files

Short explanation of what each runnable file does:

- `create_account.py` - create a Status App account for the given `username` and `password`. Example runs:
  - `python create_account.py -u snt-maxxer -p StatusApp#123`
  - `python create_account.py --username snt-maxxer --password StatusApp#123`
  - `python create_account.py` works if you have added `STATUS_USERNAME` and `STATUS_PASSWORD` in your `.env` file.
- `download.py` - download all messages and overall community info from the specified Status App channels in `config.yaml`.
- `upload.py` - upload data from `download.py` to Postgres.
