# Monitoring

The Status Bot can store the messages and Community information to allow some analytics.

## Received messages

The messages received by the bot account can be store in the database with the module `receiver`.

Data from `Messages` and `Chats` are hashed with sha256 and a pepper, to avoid storing information openly.

### Messages

| Field | Type | Hashed | Description |
|----|----|----|---|
| id | String | Hashed | Message Id |
| whisper_timestamp | - | DateTime | Timstamp of reception by the last network node |
| from_ | String | Hashed | Address of the sender |
| alias | String | Hashed | User Alias |
| seen | Boolean | - | Flag indicating if the message has been seen |
| rtl | Boolean | - | Flag indicating |
| line_count | Integer | - | |
| text | String | Hashed | Content of the messages |
| chat_id | String | Hashed | Id of the chat link to this message |
| local_chat_id | String | Hashed | Chat id for the local backend instance |
| clock | BigInteger | - | Unix timestamp of the message reception |
| replace | String | - | |
| response_to | String | Hashed | User Id to whom the message is responding |
| ens_name | String | Hashed | ENS name of the sender |
| display_name | String | Hashed | Display Name of the sender |
| timestamp | DateTime | - | timestamp of the message sent |
| content_type | Integer | - | Number indicating the type of message content |
| message_type | Integer | - | Type of message |
| contact_request_state | Integer | - | |
| compressed_key | String | - | Key used to compress the message |
| received_timestamp | DateTime | - | timestamp of the message reception |

### Chats

| Field | Type | Hashed | Description |
|----|----|----|----|
| id | String | | |
| type | String | | |
| name | String | | |
| received_timestamp | DateTime | | |
| description | String | | |
| color | String | | |
| emoji | String | | |
| active | Boolean | | |
| viewers_can_post_reactions | Boolean | | |
| chat_type | Integer | | |
| timestamp | DateTime | | |
| last_clock_value | BigInteger | | |
| deleted_at_clock_value | Integer | | |
| read_messages_at_clock_value | Integer | | |
| unviewed_messages_count | Integer | | |
| unviewed_mentions_count | Integer | | |
| membership_update_events | Integer | | |
| identicon | String | | |
| muted | Boolean | | |
| mute_till | DateTime | | |
| community_id | String | | |
| category_id | String | | |
| joined | String | | |


## Community Monitoring

The module `communities_monitoring` will allow to periodically fetch information of the community the bot account has access.

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
| number_members | Integer | Total number of community members. |

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
| `id` | String | The channel's own id | | |
| `chat_id` | String | The community id and channel id joined together. Value to use to map a message to a channel. |
| `name` | String | The channel name | | |
| `description` | String | The channel description. |
| `can_post` | Boolean | Whether the account can send messages to the channel. [`chats`](./account.md#chats) only lists channels where this is `True`. |
| `can_view` | Boolean | Whether the account can read the channel. |
| `can_post_reaction` | Boolean | Whether the account can post emoji reactions. |
| `token_gated` | Boolean | Whether access to the channel is gated behind a token. |
