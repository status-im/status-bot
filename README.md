# Status Bot

## Description

This repository allow to run a Bot for the [Status App](https://status.app). The bot can be used for multiple reason:
- [Interracting with Status Chats](./docs/usage/messaging.md)
- [Monitoring Community](./docs/usage/monitoring.md)


## Setup

The recommanded deployement option is with docker compose.

### Docker deployment

The [docker compose](./docker-compose.yaml) deployement will spin 3 containers:
- Status Backend: to interract with the Logos Delivery network used by Status App.
- Status Bot: the instance of the bot
- A Postgres database

You can run it with:

```bash
docker-compose up -d --build
```
it will require a `.env` file for secrets and `config.yaml`. The configuration is detailed in [the documentation](./docs/usage//configuration.md).

### Python

You can also run the bot with python, it will require a Status Backend instance available.

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

- `BOT_DISPLAY_NAME`
- `BOT_PASSWORD`
- `BOT_MNEMONIC_PHRASE`



# Guidelines

Things to keep in mind when building projects:

1. **Wrong recovery phrase** can create a new account by accident. To recover the account you must correctly write the phrase.

2. **Dynamic** `chats`, `communities` and `contacts` properties. If you log in to the account without a backup the properties will be empty **but will be populated automatically** if a message in a chat or community appears.

3. **Display name is not the same as username**. In Status App a display name is the **curent username** of active account. This means that if you have the same profile logged in with Python, Status Desktop and Status Mobile you can have 3 different usernames **based on your current device**. If an account is logged in from more than one device, the display name will change based on the currently used one (when messaging). This feature can be handy to distinguish if a bot or an actual user is logged in to the account. **Profile pictures work in a similar way to display names**

4. Community join requests do not work properly due to `status-go` issues. For latest updates, please monitor [`status-im/status-bot` issue #9](https://github.com/status-im/status-bot/issues/9). The fastest way to get in to a community is to manually log in with the Bot account and send a via Status App. Once the account is accepted, the bot can log in and start running. The community and chat information will appear in (2) as the messages come in.

5. To monitor for new messages, the account **must  always be logged in**. Log out of the account only if you do not want to receive messages.

6. **Token gated chats have an impact on the entire community**. You must provide an [Infura Token](https://www.infura.io/) and [Coingecko API key](https://www.coingecko.com/) during `login`. If wallet credentials are left out, then the community will not appear in (2) properties instead of the token gated chats only.
