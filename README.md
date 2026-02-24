# [Status App Monitoring](https://status.app/)

Monitoring tool for Status App communities

# Setup

## Docker

1. Login to `harbor.status.im`. Your password is your Harbor **CLI secret**.

```bash
docker login harbor.status.im
```

2. Run `docker-compose.yaml` file

```bash
docker compose up
```

## Python
1. Setup environment
```bash
conda create -n status-monitoring python=3.12
```

2. Install requirements

```bash
pip install -r requirements.txt
```

## Files

- `create_account.py` - create a Status App account for the given `username` and `password`. Example run:

```bash
python create_account.py -u snt-maxxer -p StatusApp#123
```

```bash
python create_account.py --username snt-maxxer --password StatusApp#123
```