# Account

The account class allows you to easily work with a Status account.

## Display name

The **display name** is the human‑readable identifier for a Status account. It is used when creating an account, resolving an existing account during [`login`](./account.md#loginpassword-key_uidnone-display_namenone), and when updating the account name through the [`display_name`](./account.md#display_name) property.

Display names must follow strict validation rules enforced by the library and expected by the Status application. A valid display name must satisfy all of the following conditions:

- It may contain **uppercase letters (`A–Z`)**
- It may contain **numbers (`0–9`)**
- It may contain **hyphens (`-`)**
- It may contain **underscores (`_`)**
- It must be **at least 5 characters long**
- It **cannot be more than 24 characters long**
- It **cannot start or end with a space**

Characters such as spaces, punctuation, emojis, or other symbols are **not allowed**.

### Valid examples

```
alpha_01
STATUS-01
bot_user_5
HELLO123
node-42
```

### Invalid examples

| Example | Reason |
|-------|--------|
| `bot` | Too short (minimum length is 5) |
| ` mybot` | Leading space |
| `mybot ` | Trailing space |
| `bot!123` | Contains invalid character `!` |
| `bot user` | Spaces are not allowed |

If a display name does not follow these rules, a **`ValueError`** will be raised by the account validation logic.

## Backups

Backup files (`.bkp`) can be both created in [Status App](https://our.status.im/status-desktop-v2-35-local-backups-new-home-page-performance-boosts-and-more/) and the [Python SDK](./account.md#backup). Status Backend backup folder is exposed in a Docker volume so users can:

- **Upload backup** - by dropping`.bkp` files in the `backups` folder locally (linked to Status Backend Docker container). Backups are automatically uploaded if a [`mnemonic` is provided during `login`](./account.md#loginpassword-key_uidnone-display_namenone-mnemonicnone).
- **Create backup** - by using [`backup()`](./account.md#backup) or creating one in [Status App](https://our.status.im/status-desktop-v2-35-local-backups-new-home-page-performance-boosts-and-more/).

**Note**: Status App will not automatically backup messages. This has to be manually overridden on the app. When using the Python SDK, the messages are automatically stored in the `.bkp` files.

## Methods

### `login(password, key_uid=None, display_name=None, mnemonic=None)`

Login to an existing Status account. If the account does not exist in the initialized data directory, a new account will be created and automatically logged in. After a successful login, the decentralized messenger service is automatically started so the account can send and receive messages.

An account can also be recovered if the `mnemonic` is passed.

| Name | Type | Required | Description |
|-----|-----|-----|-------------|
| `password` | `str` | Yes | Password used to encrypt the account |
| `key_uid` | `str` | Yes* | Unique key identifier of the account. If provided, the account will be logged in directly using this identifier. If not provided, then you must use `display_name` and `password` to login. |
| `display_name` | `str` | Yes* | Display name of the account. Used to resolve the `key_uid` if it is not provided, or to create a new account if one does not already exist. This field is required if an account needs to be recovered with `mnemonic`. |
| `mnemonic` | `str` | No | The mnemonic from [`info`](./account.md#info). Use this field with `password` and `display_name` to recover the account. If you have [`.bkp`](./account.md#backup) files, in the backup Docker volume they will be automatically picked up and loaded.<br>**Note**: You can pass a different `display_name` but that will be internal only. When an account is recovered setting [`display_name`](./account.md#display_name) can be buggy. Ideally when recovering the account, use the original `display_name` of the account. |

Returns the current `Account` instance, allowing method chaining.

Login with `display_name`:
```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)
```

**Note**: This assumes that `display_name` and is unique for every `key_uid`. If there are duplicated `display_names` then the first found match will be used. You can log in with `key_uid` if you have `display_name` duplicates.

Login with `key_uid`:
```python
from bot import Account

account = Account()
params = {
    "key_uid": "0xff2c3...",
    "password": "SNTPUMP"
}
account.login(**params)
```

Recover account:

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP",
    "mnemonic" : "phrase_1 phrase_2 phrase_3 phrase_4 phrase_5 phrase_6 phrase_7 phrase_8 phrase_9 phrase_10 phrase_11 phrase_12"
}
account.login(**params)
```

**Note**: When in recovery mode, the display name is updated on Status App as well so it is consistent locally and to other users.



### `logout()`

Logout from the currently logged-in Status account. This method also clears the internal account state and stops the active messenger session. This function is also supported in `del` and when the script automatically finishes.

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

# Optional - even if not specified __del__ will log you out
account.logout()
```

Returns the current `Account` instance. This allows chaining additional operations if needed.

**Note**: Currently `logout` works for a single sign in and may break because it does not listen for [`signals`](./account.md#signal).


### `send_message(chat_id, message)`

Send a text message to a specific chat. This method currently supports **text messages only**.

| Name | Type | Required | Description |
|-----|-----|-----|-------------|
| `chat_id` | `str` | Yes | Identifier of the chat where the message will be sent. All available chat IDs can be obtained from the [`chats`](./account.md#chats) property. |
| `message` | `str` | Yes | The text message to send. |

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

# This is under the assumption you already have a contact / joined a community
chat = account.chats[0]
account.send_message(chat["id"], "Hello from my Status bot!")
```

### `get_messages(chat_id, start_timestamp=None, end_timestamp=None)`

Retrieve messages from the specified chat within an optional time range. Messages are returned in **descending order** (newest to oldest). The method automatically paginates through the backend until all messages in the specified range are collected. This method is ideal for backfilling, [batch processing](https://aws.amazon.com/what-is/batch-processing/) or [micro batch processing](https://www.dremio.com/wiki/micro-batch-processing/).

Messages can be fetched from:
- **Direct messages** - current contacts and contacts that were later removed
- **Community channels** - the bot must have read access from the admin

| Name | Type | Required | Description |
|-----|-----|-----|-------------|
| `chat_id` | `str` | Yes | Identifier of the chat. All available chat IDs can be obtained from the [`chats`](./account.md#chats) property. |
| `start_timestamp` | `datetime.datetime` | No | The earliest timestamp to include. Messages older than this value will stop the fetch process. |
| `end_timestamp` | `datetime.datetime` | No | The latest timestamp to include. Messages newer than this value will be skipped. |

Returns `list[dict]` containing message objects. Timestamp fields returned by the backend are automatically converted into `datetime.datetime` objects.

```python
from bot import Account
import datetime

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

chat = account.chats[0]

messages = account.get_messages(
    chat_id=chat["id"],
    start_timestamp=datetime.datetime(2024, 1, 1)
)

for message in messages:
    print(f"{message['timestamp']}\t{message['text']}")
```

**Note**: If there are missing messages in a chat that might be because the node (Status Backend) has not received them yet. They may appear later.

### `listen_messages()`

Listen for new incoming messages **in real time**. This method yields raw message events as they are received from the Status Backend [signal](./account.md#signallisten) `messages.new`. This method is ideal for developing real time chat applications

```python
from bot import Account
import datetime
# For terminal readability only
from rich import print as rprint
from rich.pretty import Pretty

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

for msg in account.listen_messages():
    rprint(Pretty(msg))
```

**Note**: If you receive multiple messages at once, `contacts` and `chats` will grow.

### `add_contact(public_key, display_name=None)`

Send a contact request or approve an existing contact request. The mode depends on how the contact shows up in [`contacts`](./account.md#contacts). Best practice would be to look at the the following [`contacts`](./account.md#contacts) keys:

- `has_added_us` - `bool` value to check if the other user has added the account as a friend
- `added` - `bool` value to check if the account has added the other user as a friend
- `mutual` - `bool` value to check if the account and other user are in contacts
- `contact_state` - `str` value to see the account's current state
- `external_contact_state` - `str` value to see the other user's state as it is in your node

Modes:

- **Approve mode** - `has_added_us` is `True` and `added` is `False`
- **Add mode** - `has_added_us` is `False`

| Name | Type | Required | Description |
|-----|-----|-----|-------------|
| `public_key` | `str` | Yes | The contact's Status public key. |
| `display_name` | `str` | Yes / No | Display name for the contact. If the contact already exists in [`contacts`](./account.md#contacts), the `display_name` parameter is optional and the existing name will be reused. If the contact has **never interacted with the bot before**, `display_name` must be provided so the contact can be created locally. |

Returns the current `Account` instance, allowing method chaining.

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

# Send a contact request
account.add_contact(
    public_key="0x04ebcad...",
    display_name="nickninov"
)
```

### `remove_contact(public_key)`

Remove a contact or decline a pending contact request. The mode depends on how the contact shows up in [`contacts`](./account.md#contacts). Best practice would be to look at the the following [`contacts`](./account.md#contacts) keys:

- `has_added_us` - `bool` value to check if the other user has added the account as a friend
- `added` - `bool` value to check if the account has added the other user as a friend
- `mutual` - `bool` value to check if the account and other user are in contacts
- `contact_state` - `str` value to see the account's current state
- `external_contact_state` - `str` value to see the other user's state as it is in your node

Modes:

- **Remove** - `has_added_us` is `True` and `added` is `True`
- **Reject mode** - `has_added_us` is `True`

| Name | Type | Required | Description |
|-----|-----|-----|-------------|
| `public_key` | `str` | Yes | The contact's Status public key. This value corresponds to the key used in [`contacts`](./account.md#contacts). |

Returns `bool`.

| Value | Meaning |
|------|--------|
| `True` | The contact was successfully removed or the request was declined. |
| `False` | The contact does not exist or was already removed. |

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

# NOTE: contacts are returned as a dict for 
# internal class checks and scalability
contact = list(account.contacts.values())[0]

removed = account.remove_contact(contact["public_key"])
print(f"Removed: {removed}")
```

### `send_request_community(url)`

Send a request to join a community using its invitation URL. The method parses the shared Status community URL and submits a join request using the currently logged-in account. The account's [wallet address](./account.md#info) is provided to the community.

**This method works with community invites instead of specific community channel ones. Method is currently unstable.**

| Name | Type | Required | Description |
|-----|-----|-----|-------------|
| `url` | `str` | Yes | The shared Status community invitation URL. |

Returns `datetime.datetime` representing when the join request was submitted.

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

account.send_request_community(
    "https://status.app/c/community-invite-link"
)
```
### `backup()`

Create a **local backup file** (`.bkp`) for the currently logged‑in account. The backup is generated by the Status Backend and stored inside the configured Docker backup volume. Each file is uniquely associated with an account. If the backup creation fails, an **exception will be raised**.

Returns `str` representing the **Docker path** of the generated backup file. The returned path refers to the **Docker container path** where the backup was created. If the backup directory is mounted as a Docker volume, the file will also appear on the host machine in the mapped folder.

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

backup_path = account.backup()
print(f"Backup created at: {backup_path}")
```

## Properties

### `available_accounts`

Returns all Status accounts that are **locally available** in the initialized data directory. These accounts are detected when the `Account` class is initialized.

This property is useful when you want to:
- inspect which accounts exist locally
- retrieve a `key_uid` for login
- display metadata about stored accounts

**You will have to know the passwords for the given `key_uid`.**

Returns `list[dict]`.

```python
from bot import Account
# For terminal readability only
from rich import print as rprint
from rich.pretty import Pretty

account = Account()

rprint(Pretty(account.available_accounts))
```

### `info`

Provides information about the currently logged-in account. If `login()` has not been called, accessing this property will raise an exception. Returns `dict` containing account metadata.

| Key | Type | Description |
|----|----|-------------|
| `public_key` | `str` | Public key that uniquely identifies the account. |
| `url` | `str` | The URL that can be shared with other users. |
| `emojis` | `str` | Emoji hash associated with the account identity. |
| `key_uid` | `str` | Internal Status key identifier for the account. |
| `compressed_key` | `str` | The chat key as it is in Status App. |
| `mnemonic` | `str` | Mnemonic phrase used to generate the account keys. |
| `display_name` | `str` | Display name of the account. |
| `password` | `str` | Password used to encrypt the account locally. |
| `wallet_address` | `str` | Ethereum wallet address associated with the account. |
| `logged_in_timestamp` | `datetime.datetime` | Timestamp when the account successfully logged in. |

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

print(account.info)
```

### `contacts`

This property returns contacts that have interacted with the account, including:

- active contacts.
- users who sent a contact request.
- users whose contact request was sent by the bot.
- contacts that were previously removed. If the contact is removed on both sides then it might disappear from the property.

The property always fetches the latest state directly from the Status Backend. The lifecycle is as follows:
  - `none` - no relationship
  - `sent` - request sent by this account
  - `received` - request received from another account
  - `mutual` - both users have added each other

Returns `dict[str, dict]` where the key is the contact's **public key**. This makes internal searching for account specific information faster.

| Key | Type | Description |
|----|----|-------------|
| `public_key` | `str` | Public key that uniquely identifies the contact. |
| `url` | `str` | The URL that can be shared with other users. |
| `chat_id` | `str` | Chat identifier used for direct messaging. |
| `key_uid` | `str` | Internal compressed key identifier used by Status Backend. |
| `emojis` | `str` | Emoji hash associated with the contact identity. |
| `contact_state` | `str` | Current state of the contact relationship (`none`, `mutual`, `sent`, `received`, `dismissed`). |
| `external_contact_state` | `str` | How the contact relationship appears from the other user's perspective. |
| `has_added_us` | `bool` | Whether the other user has added this account as a contact. |
| `added` | `bool` | Whether this account has added the other user as a contact. |
| `mutual` | `bool` | Whether both users have added each other. |
| `display_name` | `str` | The current display name of the contact. |
| `bio` | `str` | The contact's profile bio. |
| `wallet_address` | `str` | Ethereum wallet address associated with the contact. |
| `last_updated` | `datetime.datetime` | Timestamp when the contact information was last updated. |

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

contacts = account.contacts

for contact in contacts.values():
    print(contact["display_name"], contact["contact_state"])
```

### `communities`

Get all communities that the account is currently a member of. This property always fetches the **latest community state** directly from the Status Backend. This ensures dynamic values such as community metadata, members, and channel permissions are always up to date.

Each community contains information about:

- community metadata (name, description, tags)
- membership status
- number of members
- available channels and their permissions

Returns `list[dict]` where each element represents a community.

| Key | Type | Description |
|----|----|-------------|
| `id` | `str` | Unique identifier of the community. |
| `url` | `str` | The URL that can be shared with other users. |
| `name` | `str` | Name of the community. |
| `verified` | `bool` | Whether the community is verified. |
| `description` | `str` | Community description. |
| `dialog` | `str` | Intro message shown when joining the community. |
| `leaving_message` | `str` | Message shown when leaving the community. |
| `tags` | `list[str]` | Tags associated with the community. |
| `is_member` | `bool` | Whether the account is currently a member of the community. |
| `joined_timestamp` | `datetime.datetime` | Timestamp when the account joined the community. |
| `requested_timestamp` | `datetime.datetime` | Timestamp when the join request was submitted. |
| `encrypted` | `bool` | Whether the community messaging is encrypted. |
| `members` | `int` | Total number of community members. |
| `channels` | `list[dict]` | List of channels available in the community. |

Each channel contains:

| Key | Type | Description |
|----|----|-------------|
| `id` | `str` | Channel identifier inside the community. |
| `chat_id` | `str` | Combined community + channel ID used for sending messages. |
| `url` | `str` | The URL that can be shared with other users. |
| `name` | `str` | Channel name. |
| `description` | `str` | Channel description. |
| `permissions` | `dict` | Permissions for the channel. |

Channel `id` values can be used directly with [`send_message`](./account.md#send_messagechat_id-message)

Channel permissions:

| Key | Type | Description |
|----|----|-------------|
| `posting` | `bool` | Whether the account can post messages in the channel. |
| `viewing` | `bool` | Whether the account can view messages in the channel. |
| `reactions` | `bool` | Whether the account can react to messages. |
| `token_gated` | `bool` | Whether the channel requires a token to participate. |

```python
from bot import Account

account = Account()
account.login("status-app-bot", "SNTPUMP")

for community in account.communities:
    print(community["name"], community["members"])

    for channel in community["channels"]:
        print(f"\t#{channel['name']} posting: {channel['permissions']['posting']}")
```

### `chats`

Get all chats that the account can **send messages to**. This includes:
- [`contacts`](./account.md#contacts) — direct messages with users
- [`communities`](./account.md#communities) — community channels where the account has **posting permission**
- Group chats that the account is in

Returns `list[dict]` where each `dict` represents a chat that can be used with [`send_message`](./account.md#send_messagechat_id-message) and [`get_messages`](./account.md#get_messageschat_id-start_timestampnone-end_timestampnone).

| Key | Type | Description |
|----|----|-------------|
| `type` | `str` | Type of chat (`contact`, `channel` or `group_chat`). |
| `id` | `str` | Chat identifier used when sending messages. |
| `name` | `str` | Either the display name of the user or the community channel name. |

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

# This is under the assumption you already have a contact / joined a community
for chat in account.chats:
    print(f"{chat['type']}\t{chat['name']}\t{chat['id']}")
```

### `signal`

The property exists in `Account` because signals require an **active logged‑in session**. Attempting to use signals before calling `login()` will raise an exception. Signals are low‑level events emitted by the Status Backend. Examples include:

- `messages.new`
- `message.delivered`
- `node.ready`
- `node.started`
- `node.login`
- `node.stopped`

The property exposes two primary methods:

- `signal.get()` — fetch a single event. If the event is not found, you may end up in an infinite loop.
- `signal.listen()` — stream events continuously. Example usage of this is found in [`listen_messages()`](./account.md#listen_messages)

### `display_name`

Get or update the current display name of the logged‑in account.

Returns `str` when reading the property.

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

# Get the current display name
print(account.display_name)
```

You can update the display name by assigning a new value:

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

# Change the display name
account.name = "status_bot_42"
print(account.display_name)
```

**Note**: Next time you login with the changed display name, you will have to put in the new display name, instead of the initial one.

### `bio`

Get or update the **bio** of the currently logged‑in account. The length of the bio (as in Status App) is 240 characters.

Returns `str` when reading the property.

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

# Read the current bio
print(account.bio)
```

The value assigned to `bio` will automatically be converted to a string before being sent to the backend. You can update the bio by assigning a new value:

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

# Update the bio
account.bio = "Monitoring Status communities and chats"
print(account.bio)
```

You can also **clear the bio** by deleting the property:

```python
from bot import Account

account = Account()
params = {
    "display_name": "status-app-bot",
    "password": "SNTPUMP"
}
account.login(**params)

# Clears the bio - same as: 
# account.bio = ""
# account.bio = None
del account.bio
```

### `logger`

Provides access to the internal **Python logger** for monitoring the lifecycle of the account and backend operations such as login, account creation, messenger startup, and recovery.

Returns `logging.Logger`.

Default logger configuration:

- **Name**: `status-bot`
- **Level**: `INFO`
- **Output**: standard output (terminal)

Example:

```python
from bot import Account

account = Account()

account.logger.info("Starting Status bot")
account.logger.warning("This is a warning")
account.logger.error("Something went wrong")
```
