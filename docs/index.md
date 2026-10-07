# Status Bot

The Status Bot is a Python tool communicating with the Status-backend to automate some actions.

## Architecture

```mermaid
graph TB

   BACKEND[Status Backend]
   BOT[Status Bot]
   DB[Database]
   subgraph external[External Services]
        COINGECKO[CoinGecko]
        INFURA[Infura]
        ALCHEMY[Alchemy]
    end

   BOT --> BACKEND
   BACKEND --> |coingecko_api_key| COINGECKO
   BACKEND --> |infura_token| INFURA
   BACKEND --> |alchemy_token| ALCHEMY
   BOT --> DB
```

The Status Bot use [status-python-sdk](https://github.com/status-im/status-python-sdk) for the interraction with Status Backend.

The Status-Backend use external services:

* CoinGecko - Optional to get token price
* EVM access - Required to interract with Token Gated community. Only Infura EVM works.
* Alchemy - Optional to get account transactions 

## Account Setup

The Bot require a Status Account to work.

### Intializing new account

The account can be initialized at startup with the following configuration:

```yaml
bot:
    name: 'Display Name'
    chat_key: 'zQ3...Example'
    password: 'YourPassword'
    mnemonic_phrase: 'word1 word2 ... word12'
    infura_token: 'Your Infura token'
    alchemy_token: 'Your Alchemy token'
    coingecko_api_key: 'Your Coingecko API key'
    bot_hash_pepper: 'your-secret-pepper'
```

### Importing Status Account

The account can also be imported from the Status Application. It first need to export a backup, then import it in the docker container under `/backups`.

> Note: the account backup need to also be imported in Status Backend

The full configuration explaination can be found in the [configuration](deployment/configuration.md) page.
