# Messaging API

The bot exposes a REST endpoint for sending messages, managing contacts, and querying chats.

## Interactive docs

| Tool | URL |
|------|-----|
| Swagger UI | `http://localhost:8081/docs` |
| ReDoc | `http://localhost:8081/redoc` |
| OpenAPI JSON | `http://localhost:8081/openapi.json` |

## Authentication

If `api.api_key` is configured in `config.yaml`, all requests (except `/health`, `/docs`, `/redoc`, and `/openapi.json`) must include the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-secret-key" http://localhost:8081/api/v1/chats
```

Requests without a valid key return `401 Unauthorized`:

```json
{"detail": "Invalid or missing API key"}
```

## Endpoints

### `GET /health`

Health check.

```bash
curl http://localhost:8081/health
```

Response `200`:
```json
{"status": "healthy"}
```

### `POST /api/v1/contacts`

Add a contact (send friend request).

```bash
curl -X POST http://localhost:8081/api/v1/contacts \
  -H "Content-Type: application/json" \
  -d '{"public_key": "0x...", "display_name": "Alice"}'
```

Request body:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `public_key` | `string` | Yes | Contact's public key |
| `display_name` | `string` | No | Display name (required if not already a contact) |

Response `201`:
```json
{"status": "ok"}
```

Error `400` — missing or invalid fields.

### `DELETE /api/v1/contacts/{public_key}`

Remove a contact.

```bash
curl -X DELETE http://localhost:8081/api/v1/contacts/0x...
```

Response `200`:
```json
{"status": "ok"}
```

Error `404` — contact not found or already removed.

### `GET /api/v1/chats`

List all available chats (contacts, community channels, and group chats).

```bash
curl http://localhost:8081/api/v1/chats
```

Response `200`:
```json
[
  {"type": "contact", "id": "0x...", "name": "Alice"},
  {"type": "channel", "id": "0x...", "name": "Community #general"},
  {"type": "group_chat", "id": "0x...", "name": "Group Chat Name"}
]
```

Each chat has:
| Field | Type | Description |
|-------|------|-------------|
| `type` | `string` | `contact`, `channel`, or `group_chat` |
| `id` | `string` | Chat ID (used in message endpoints) |
| `name` | `string` | Human-readable name |

### `GET /api/v1/chats/{chat_id}/messages`

Get messages from a chat. Messages are returned newest-first.

```bash
curl "http://localhost:8081/api/v1/chats/0x.../messages"
```

Optional query parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_timestamp` | ISO 8601 | Only messages after this timestamp |
| `end_timestamp` | ISO 8601 | Only messages before this timestamp |

```bash
curl "http://localhost:8081/api/v1/chats/0x.../messages?start_timestamp=2025-01-01T00:00:00&end_timestamp=2025-06-01T00:00:00"
```

Response `200` — array of message objects.

### `POST /api/v1/chats/{chat_id}/messages`

Send a text message to a chat.

```bash
curl -X POST http://localhost:8081/api/v1/chats/0x.../messages \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from the bot!"}'
```

Request body:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | `string` | Yes | Message content |

Response `201`:
```json
{"status": "ok"}
```

### `GET /api/v1/communities`

Return all the communities.

```bash
curl http://localhost:8081/api/v1/communities
```

### `POST /api/v1/communities/request`

```bash
curl -X POST http://localhost:8081/api/v1/communities/request \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from the bot!"}'
```

Request body:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | `string` | Yes | Community url |

Response `201`:
```json
{
    "status": "request_send"
    "request_time": time of the request
}
```

## Error handling

All errors return a JSON body with a `detail` field:

```json
{"detail": "Contact not found or already removed"}
```

| Status | Meaning |
|--------|---------|
| `400` | Bad request (invalid input, missing fields, wrong format) |
| `404` | Resource not found (contact, chat) |
| `422` | Validation error (malformed request body) |
| `500` | Internal server error |
