# [Status App Monitoring](https://status.app/)

Monitoring tool for Status App communities.

# Setup

## Environment Variables

- `POSTGRES_USERNAME` - Postgres username.
- `POSTGRES_PASSWORD` - Postgres password.
- `POSTGRES_DATABASE` - The database name in the Postgres connection.
- `POSTGRES_HOST` - The Postgres host name that will be remotely connected to.
- `POSTGRES_PORT` - The Postgres port that will be remotely connected to.
- `STATUS_DISPLAY_NAME` - The Status display name that will be used to create an account.
- `STATUS_PASSWORD` - The Status password that will be used to create an account.
- `STATUS_MNEMONIC` - The mnemonic used to recover the account. If passed a `.bkp` file will be loaded as well. Use this when you want to login to a bot account via Status App, join a community / leave community and export the `.bkp` file.
- `STATUS_INFURA_TOKEN` - [Infura token](https://www.infura.io/) is required for **token gated communities**
- `STATUS_COINGECKO_API_KEY` - [Coingecko API Key](https://www.coingecko.com/) is required for **token gated communities**

## Docker deployement

You can use the `docker-compose.yaml` to run the project.

Example of `.env` file to use
```
# Status Backend connection
STATUS_DISPLAY_NAME = "bot-status"
STATUS_PASSWORD = "ChangeThisPassword"
STATUS_MNEMONIC= "test test test test test test test test test test test test"

# Necessary for communities that have tokens
STATUS_INFURA_TOKEN = "Token from https://www.infura.io/"
STATUS_COINGECKO_API_KEY = "Token from https://www.coingecko.com/"

# Database config
POSTGRES_HOST=database
POSTGRES_PORT=5432
POSTGRES_DATABASE=status-bot
POSTGRES_USERNAME=status
POSTGRES_PASSWORD=ChangeThisOneAlso
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

# Backups

If you have already created a Status account and want to use it with it's current data, please make sure you export the `.bkp` file and put it in folder **backups** and have the following `.env` variables:

- `STATUS_DISPLAY_NAME`
- `STATUS_PASSWORD`
- `STATUS_MNEMONIC`

# Files

- `monitor.py` - Status community message monitoring. It will download and upload messages in parallel.
