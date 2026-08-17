from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from status_bot.modules.base import BaseModule, ModuleType

import os

class AddContactRequest(BaseModel):
    public_key: str
    display_name: Optional[str] = None


class SendMessageRequest(BaseModel):
    text: str

class SendRequestCommunityRequest(BaseModel):
    url: str

class MessagingModule(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.SERVICE

    def on_start(self):
        app: FastAPI = self.context.shared_state["fastapi_app"]
        self._setup_routes(app)

    def _setup_routes(self, app: FastAPI):
        account = self.context.account

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
            try:
                return account.get_messages(chat_id, start_timestamp, end_timestamp)
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.post("/api/v1/chats/{chat_id}/messages", status_code=201)
        def send_message(chat_id: str, payload: SendMessageRequest):
            if not payload.text:
                raise HTTPException(status_code=400, detail="Message text is required")
            msg_id = account.send_message(chat_id, payload.text)
            return {"status": "ok", "id": msg_id}

        @app.get("/api/v1/communities")
        def get_communities():
            return account.communities

        @app.post("/api/v1/backup", status_code=201)
        def backup():
            file_path = account.backup()
            st = os.stat(file_path)
            created = datetime.fromtimestamp(st.st_ctime)
            return {"status": "ok", "created_timestamp": created, "file_path": file_path}

    def execute(self):
        self.context.stop_event.wait()
