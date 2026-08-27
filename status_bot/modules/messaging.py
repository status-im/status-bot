from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from status_bot.modules.base import BaseModule, ModuleType


class AddContactRequest(BaseModel):
    public_key: str
    display_name: Optional[str] = None


class SendMessageRequest(BaseModel):
    text: str

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
            return account.contacts

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

        @app.get("/api/v1/communities")
        def get_communities():
            return account.communities

        @app.post("/api/v1/communities/request", status_code=201)
        def send_request_community(payload: SendRequestCommunityRequest):
            if not payload.url:
                raise HTTPException(status_code=400, detail="Community url is required")
            request_time = account.send_request_community(payload.url)
            if not request_time:
                raise HTTPException(status_code=400, detail="Error when trying to send the community request")
            return {"status": "request send", "request_time": request_time}

    def execute(self):
        self.ctx.stop_event.wait()
