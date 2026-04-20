# Status Python SDK

![Status Python SDK header image](./images/overview-header.png)

The initial Python Status Backend was built with testing in mind, instead of easy developer access. The objective of this repository is to make a SDK that is:

- **light** - as less external packages when it comes to working with Status App
- **fast** - quick to get started with Status Python
- **documented** - clear explanations of what was done and **why it was done in a specific way**.

Currently this repository is not on [PyPi](https://pypi.org/) but will be added when core functionality has been devleoped and tested.

## How it works

```mermaid
graph TB
   subgraph backend[status-im/status-go]
       subgraph Endpoints[Network: status-bridge]
           RPC[RPC]
           HTTP[REST]
           SOCKET[Web Socket]
       end
       Vol[(Backup)]
   end


   subgraph bot[Python SDK]
        REQUIREMENTS[requirements.txt]
        SDK[class Account]
        SIGNAL[class Signal]
    end

    subgraph external[External Services]
        COINGECKO[CoinGecko]
        EVM
    end

   SDK --> SIGNAL
   SDK --> |Port 8080| RPC
   SDK --> |Port 8080| HTTP
   SIGNAL --> |Port 8080| SOCKET
   SDK --> Vol
   RPC --> |coingecko_api_key| COINGECKO
   RPC --> |infura_token| EVM
```

## Setup

To access Python funcitonality you will have to set up [Status Backend](https://github.com/status-im/status-go/). Easiest and fastest way to get it running would be with [Docker](https://www.docker.com/products/docker-desktop/).

```mermaid
sequenceDiagram
    actor User
    participant Docker
    participant Python@{"alias": "status-im/status-bot"}
    participant Github@{"alias": "status-im/status-go" }
    
    User ->> Docker: docker-compose up
    Docker ->> Github: Fetch Image
    Docker ->> Docker: Build
    User ->> Docker: Run container
    User ->> Python: initialize module
    Note over User,Python: from bot import Account<br>account = Account()
```
