from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from status_sdk.exceptions import MessageTooLongError, SendContentError

from status_bot.modules.base import BaseModule, ModuleType
from status_sdk.models import Message


class AddContactRequest(BaseModel):
    public_key: str
    display_name: Optional[str] = None


class SendMessageRequest(BaseModel):
    text: str


class SendMessageToUserRequest(BaseModel):
    """Discord webhook-inspired payload to send a message to a contact."""

    content: Optional[str] = None
    embeds: Optional[list[dict]] = None


def _render_embeds_to_text(embeds: list[dict]) -> str:
    """Render a list of Discord-style embeds into plain text for Status App."""
    parts: list[str] = []
    for embed in embeds or []:
        lines: list[str] = []
        author = embed.get("author") or {}
        if author.get("name"):
            lines.append(author["name"])
        if embed.get("title"):
            lines.append(embed["title"])
        if embed.get("description"):
            lines.append(embed["description"])
        for field in embed.get("fields") or []:
            name = field.get("name", "")
            value = field.get("value", "")
            if name and value:
                lines.append(f"{name}: {value}")
            elif value:
                lines.append(value)
        footer = embed.get("footer") or {}
        if footer.get("text"):
            lines.append(footer["text"])
        if lines:
            parts.append("\n".join(lines))
    return "\n---\n".join(parts)


class SendRequestCommunityRequest(BaseModel):
    url: str


class MessagingModule(BaseModule):
    @property
    def module_type(self) -> set[ModuleType]:
        return {ModuleType.SERVICE}

    def on_start(self):
        app: FastAPI = self.ctx.shared_state["fastapi_app"]
        self._setup_routes(app)

    def _setup_routes(self, app: FastAPI):
        account = self.ctx.account

        @app.get("/health")
        def health():
            return {"status": "healthy"}

        @app.get("/api/v1/contacts")
        def get_contacts():
            return {
                key: contact for key, contact in account.contacts.items() if contact.get("mutual")
            }

        @app.post("/api/v1/contacts", status_code=201)
        def add_contact(payload: AddContactRequest):
            try:
                account.add_contact(payload.public_key, payload.display_name)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            return {"status": "ok"}

        @app.delete("/api/v1/contacts/{public_key}")
        def remove_contact(public_key: str):
            if not account.remove_contact(public_key):
                raise HTTPException(
                    status_code=404,
                    detail="Contact not found or already removed",
                )
            return {"status": "ok"}

        @app.get("/api/v1/chats")
        def get_chats():
            return account.chats

        @app.get("/api/v1/chats/{chat_id}/messages")
        def get_messages(
            chat_id: str,
            start_timestamp: Optional[str] = None,
            end_timestamp: Optional[str] = None,
        ):
            start = None
            end = None
            if start_timestamp:
                try:
                    start = datetime.fromisoformat(start_timestamp)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid start_timestamp, use ISO format",
                    )
            if end_timestamp:
                try:
                    end = datetime.fromisoformat(end_timestamp)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid end_timestamp, use ISO format",
                    )
            return account.get_messages(chat_id, start, end)

        @app.post("/api/v1/chats/{chat_id}/messages", status_code=201)
        def send_message(chat_id: str, payload: SendMessageRequest):
            if not payload.text:
                raise HTTPException(status_code=400, detail="Message text is required")
            account.send_message(chat_id, payload.text)
            return {"status": "ok"}

        @app.post("/api/v1/messages/{compressed_key}", status_code=201)
        def send_message_to_user(compressed_key: str, payload: SendMessageToUserRequest):
            """Send a message to a mutual contact using its compressed key.

            The path `compressed_key` is looked up in `account.contacts`
            (falling back to the raw public key `0x...`). Only mutual
            contacts can be messaged.
            """
            text = payload.content
            if not text and payload.embeds:
                text = _render_embeds_to_text(payload.embeds)
            if not text:
                raise HTTPException(status_code=400, detail="Message content is required")
            if len(text) > 2000:
                raise HTTPException(status_code=400, detail="Message too long")

            contact = None
            for current in account.contacts.values():
                if not current.get("mutual"):
                    continue
                if current.get("compressed_key") == compressed_key:
                    contact = current
                    break
            if contact is None and compressed_key.startswith("0x"):
                for current in account.contacts.values():
                    if not current.get("mutual"):
                        continue
                    if current.get("public_key") == compressed_key:
                        contact = current
                        break
            if contact is None:
                raise HTTPException(
                    status_code=404,
                    detail="Contact not found or not a mutual contact",
                )

            try:
                account.send_message(contact["public_key"], text)
            except MessageTooLongError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except SendContentError as e:
                raise HTTPException(status_code=502, detail=str(e))
            except Exception as e:  # backend/unexpected failure
                raise HTTPException(status_code=502, detail=f"Failed to send message {e}")
            return {"status": "ok"}

        @app.get("/api/v1/communities")
        def get_communities():
            return account.communities

        @app.post("/api/v1/communities/request", status_code=201)
        def send_request_community(payload: SendRequestCommunityRequest):
            if not payload.url:
                raise HTTPException(status_code=400, detail="Community url is required")
            request_time = account.send_request_community(payload.url)
            if not request_time:
                raise HTTPException(
                    status_code=400, detail="Error when trying to send the community request"
                )
            return {"status": "request send", "request_time": request_time}

    def execute(self):
        pass

    def on_event(self, message: Message) -> None:
        pass
