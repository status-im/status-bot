# Engagement

The Engagement Modules are set to help new user understand the Status App and share feedback, feature request and question with the Team.
It is composed of two modules:
* `EngagementEvent` - Response at the event the Bot is receiving.
* `EngagementPeriodic` - Send messages based on the contact request from the Bot.

The Engagement Module in the Status Bot is designed to automate user interactions in the Status App.
Its primary functions include:
1. Contact Request Handling
  - Automatically accepts incoming contact requests from users.
  - Sends welcome messages to new contacts, with different messages for new vs. existing users.
 2. Feedback Message Management
   - Detects messages containing feedback-related keywords (e.g., feedback).
   - Forwards valid feedback requests to a dedicated feedback group chat for team review.
   - Sends automated replies to users to acknowledge their requests.
   - Routes replies from the feedback team back to the original user.
3. Periodic Engagement
  - Sends scheduled follow-up messages to new users based on configurable delays (e.g., after 1 day, 1 week).
 4. Group Chat Coordination
   - Creates or loads a feedback group chat where the team can discuss and respond to user requests.
   - Ensures smooth two-way communication between users and the feedback team.

## Configuration

| **Setting** | **Type** | **Mandatory** | **Description** | **Example** |
|-------------|----------|--------------|----------------|----------------------------------|
| `first_messages` | `List[str]` | ✅ | Welcome messages sent to **new users** after accepting their contact request. | `["Welcome to Status 👋", "What is Status?", "Get started on Status"]` |
| `feedback_keywords` | `List[str]` | ✅ | Keywords that trigger feedback message handling (e.g., `feedback`, `help`). | `["feedback"]` |
| `helper_message` | `str` | ✅ | Message sent when a user's message **does not** match feedback keywords. | `"My goal is to help new user discover Status..."` |
| `automatic_reply` | `str` | ✅ | Automated reply sent to users when their message **matches** feedback keywords. | `"Your message has been shared with the Status Team..."` |
| `group_chat` | `dict` | ✅ | Configuration for the **group chat** where requests are forwarded. | `{ group_id: "f6ef4b29-...", participants: ["zQ3shf5QUQpCEhFwuxuCCLiujPGoCzZZvk65HRJSBiPX8LyYF"], name: "Status Test Group Ultimate" }` |
| `new_user_message_contact_request` | `str` | ✅ | Message used to identify **new user contact requests**. | `"test new user"` |
| `existing_users_messages` | `List[str]` | ✅ | Welcome messages sent to **existing users** after accepting their contact request. | `["Hey there 👋 Thanks for connecting with the Status Team bot..."]` |
| `image_folder` | `str` | ✅ | Directory where downloaded images (e.g., from user messages) are stored. | `"/app/assets/images"` |
| `periodic_messages` | `List[dict]` | ✅ | List of **scheduled follow-up messages** with delays and content. | `[ { delay: 1, message: "Bring someone you know to Status 👋..." }, { delay: 2, message: "Find your people 🌐..." } ]` |
| `group_message_text` | `str` | ❌ | Message sent to the **feedback group chat** when a new user request is forwarded. | `"A user has shared the following request. Reply to the message to transfer it to the user."` |
| `delay_type` | `str` | ❌ | Unit for periodic message delays (`days` or `minutes`). | `"minutes"` |

### `group_chat`

The `group_chat` object can contain the following object.

| **Setting** | **Type** | **Mandatory** | **Description** | **Example** |
|-------------|----------|---------------|-----------------|-------------|
| `name`      | `str` | ✅ | Name of the GroupChat | `"Feedback Group"`  |
| `participants` | `List[str]` | ✅ | List of all the contact to add in the group chat at creation. | `["zQ3s...."]` |
| `group_id` | `str` | ❌ | Chat Id of the group if it already exist | `"abcd123549-121"` |

### Periodics Messages

The field `periodic_messages` accept a list of the following object.

| **Setting** | **Type** | **Mandatory** | **Description** | **Example** |
|-------------|----------|---------------|-----------------|-------------|
| `delay` | `int` | ✅ | Delay between the contact request and the message being send. The delay is by default in days but can be overwriten with the config `delay_type` | `1` |
| `message` | `str` | ✅ | Message to send once the delay is passed | `Bring someone you know to Status 👋...` |


### Default module Configuration

Like all Periodic module, the interval of the periodic action can be configure with `interval` set the root of the module configuration

| **Setting** | **Type** | **Mandatory** | **Description** | **Example** |
|-------------|----------|---------------|-----------------|-------------|
| `interval`  | `int` | ❌ | Interval (in minutes) for running the periodic engagement task. | `1` |


## Database Models

This module store in the database the following object.

### `FeedbackMessage`

**Table:** `feedback_message` — Stores user feedback requests and their corresponding responses from the GroupChat.

| **Field** | **Type** | **Nullable** | **Description** |
|-----------|----------|--------------|----------------|
| `id` | `String` | ❌ | Unique identifier for the feedback message (matches the original message ID from the Status App). |
| `public_key` | `String` | ❌ | Public key of the **user** who sent the feedback request. |
| `request_message` | `String` | ✅ | The **content** of the user's feedback request. |
| `request_timestamp` | `BigInteger` | ✅ | Timestamp (Unix epoch) when the user sent the request. |
| `chat_id` | `String` | ✅ | ID of the **chat** where the request was sent. |
| `group_chat_message_id` | `String` | ✅ | ID of the message in the **feedback group chat** where the request was forwarded. |
| `response_timestamp` | `BigInteger` | ✅ | Timestamp (Unix epoch) when the Status Team **replied** to the request. |
| `response_message` | `String` | ✅ | The **content** of the Status Team's reply. |
| `reply_chat_id` | `String` | ✅ | ID of the **reply message** sent back to the user. |
| `reply_group_id` | `String` | ✅ | ID of the **group message** that triggered the reply (if applicable). |

**Why?**
- The messages id and user address is mandatory to ensures replies are routed back to the correct user.
- The message content and timestamp are kept to audit the system.


### `ContactRequest`

**Table:** `contact_request` — Stores contact requests from users and tracks their engagement status.

| **Field** | **Type** | **Nullable** | **Description** |
|-----------|----------|--------------|----------------|
| `id` | `String` | ❌ | Unique identifier for the contact request. |
| `public_key` | `String` | ❌ | Public key of the **user** who sent the contact request. |
| `request_message` | `String` | ✅ | The **message** sent by the user when requesting contact. |
| `request_timestamp` | `DateTime` | ❌ | Timestamp when the contact request was **received**. |
| `conversation_id` | `String` | ✅ | ID of the **conversation** where the request was made. |
| `last_engagement_message` | `Float` | ✅ | Timestamp of the **last engagement message** sent to the user (used for periodic follow-ups). |
| `is_new_user` | `Boolean` | ✅ | Flag indicating whether the user is **new** (`True`) or **existing** (`False`). |

**Why?**
- Manages periodic engagement and keep track of which message has been sent.
- Helps distinguish between first-time users (who receive `first_messages`) and returning users (who receive `existing_users_messages`).

## Metrics

### `status_bot_engagement_actions`

A counter that tracks user engagement actions with a type label.
It has different label based on the types of actions done:
- `received_request` – A contact request was received.
- `accepted_request` – A contact request was accepted.
- `first_messages` – Welcome message sent to a new user.
- `existing_users_messages` – Welcome message sent to an existing user.
- `invalid-feedback-query` – User message did not match feedback keywords.
- `valid-feedback-query` – User message matched feedback keywords.
- `request-transfered` – Feedback request forwarded to the group chat.
- `original-not-found` – Reply failed (original message not found in DB).
- `sent-reply` – Reply successfully sent from the group chat to user.

#### `status_bot_engagement_periodic`

A counter, that tracks periodic engagement messages with a the delay as label (e.g., 1, 7, 30).
It incremented when a scheduled follow-up message is sent to a user.


