# Monitoring

The Status Bot can store the messages and Community information to allow some analytics.

## Received messages

The messages received by the bot account can be store in the database with the module `receiver`.

Data from `Messages` are encrypted with AES-256-SIV (deterministic, authenticated) using the secret configured in `bot.encryption_key`, so no human-readable user data is stored at rest. Encrypted values carry an `enc1$` prefix; use `status_bot.modules.utils.from_encrypted_value(value, key)` to read them back.

### Messages

| Field | Type | Encrypted | Description |
|----|----|----|---|
| id | String | Encrypted | Message Id (deterministic, used for dedup) |
| whisper_timestamp | DateTime | - | Timestamp of reception by the last network node |
| from_ | String | Encrypted | Address of the sender |
| alias | String | - | User Alias (`NULL`, not provided by the SDK anymore) |
| text | String | Encrypted | Content of the messages |
| chat_id | String | Encrypted | Id of the chat link to this message |
| response_to | String | Encrypted | Id of the message this message replies to (`NULL` when not a reply) |
| content_type | Integer | - | Number indicating the type of message content (`Content` enum value: 1 text, 2 sticker, 4 emoji, 7 image, 18 bridged, …) |
| message_type | String | - | Type of chat the message was sent in: `PRIVATE`, `GROUP` or `COMMUNITY` |
| contact_request_state | Integer | - | (`NULL`, not provided by the SDK anymore) |
| compressed_key | String | - | (`NULL`, not provided by the SDK anymore) |
| received_timestamp | DateTime | - | timestamp of the message reception by the bot |

> **Upgrading from the previous HMAC-SHA256 scheme:** legacy rows are one-way hashes and can never be decrypted. Purge them before restarting with the new version: `DELETE FROM received_messages;`. The `received_chats` table is no longer part of the schema (the `ReceivedChat` model was removed) and can be dropped with `DROP TABLE IF EXISTS received_chats;`.

## Community Monitoring

The module `community_monitoring` will allow to periodically fetch information of the community the bot account has access.

The data by the Bot are the following.

### Community

| Field | Type | Description |
|----|----|----|
| id | String | Community Id |
| url | String | Url to join the community |
| name | String | Name of the community |
| verified | Boolean | Flag if the community is verified |
| tags | String | All the community tags separated by a `,` |
| is_member | Boolean | Flag indicating the community the bot has joined |
| joined_timestamp | DateTime | Timestamp when the account joined the community. `None` when the account has not joined. |
| requested_timestamp | DateTime | Timestamp when the join request was submitted. `None` when no request was made. |
| encrypted | String | Whether the community messaging is encrypted. |
| members | Integer | Total number of community members. |
| batch_timestamp | DateTime | Timestamp of the batch the community data was fetched in. |

### Channels

* `id`: Id of the channel.
* `chat_id`: Chat id of the channel.
* `community_id`: Id of the channel's community.
* `name`: Name of the channel.
* `description`: Description of the channel.
* `can_post`: Can the Bot Post into the channel.
* `can_view`: Can the Bot view the channel.
* `can_post_reaction`: Can the bot react to a Post.
* `token_gated`: Is the channel access limited with a token.


| Key | Type | Description |
|----|----|-------------|
| `id` | String | The channel's own id |
| `chat_id` | String | The community id and channel id joined together. Value to use to map a message to a channel. |
| `name` | String | The channel name |
| `description` | String | The channel description. |
| `can_post` | Boolean | Whether the account can send messages to the channel. The SDK's `chats` property only lists channels where this is `True`. |
| `can_view` | Boolean | Whether the account can read the channel. |
| `can_post_reaction` | Boolean | Whether the account can post emoji reactions. |
| `token_gated` | Boolean | Whether access to the channel is gated behind a token. |
