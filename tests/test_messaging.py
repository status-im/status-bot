from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from status_sdk.exceptions import SendContentError

from status_bot.modules.base import ModuleConfig, ModuleContext
from status_bot.modules.messaging import MessagingModule

MUTUAL_CONTACT = {
    "public_key": "0xalice",
    "chat_id": "0xalice",
    "compressed_key": "zQAliceCompressedKey",
    "mutual": True,
    "display_name": "Alice",
}

NON_MUTUAL_CONTACT = {
    "public_key": "0xbob",
    "chat_id": "0xbob",
    "compressed_key": "zQBobCompressedKey",
    "mutual": False,
    "display_name": "Bob",
}

CONTACTS = {
    "0xalice": MUTUAL_CONTACT,
    "0xbob": NON_MUTUAL_CONTACT,
}


def _make_client(contacts):
    account = MagicMock()
    account.contacts = contacts
    app = FastAPI()
    ctx = ModuleContext(
        account=account,
        config=ModuleConfig(name="messaging"),
        shared_state={"fastapi_app": app},
    )
    MessagingModule(ctx).on_start()
    return TestClient(app), account


def test_send_message_to_mutual_contact_by_compressed_key():
    client, account = _make_client(CONTACTS)

    response = client.post(
        "/api/v1/messages/zQAliceCompressedKey", json={"content": "hello there"}
    )

    assert response.status_code == 201
    assert response.json() == {"status": "ok"}
    account.send_message.assert_called_once_with("0xalice", "hello there")


def test_send_message_fallback_to_public_key():
    client, account = _make_client(CONTACTS)

    response = client.post("/api/v1/messages/0xalice", json={"content": "hi"})

    assert response.status_code == 201
    assert response.json() == {"status": "ok"}
    account.send_message.assert_called_once_with("0xalice", "hi")


def test_send_message_contact_not_found():
    client, _ = _make_client(CONTACTS)

    response = client.post("/api/v1/messages/zQUnknownCompressedKey", json={"content": "hi"})

    assert response.status_code == 404


def test_send_message_not_mutual_contact():
    client, _ = _make_client(CONTACTS)

    # Bob is in contacts but is not mutual.
    response = client.post("/api/v1/messages/zQBobCompressedKey", json={"content": "hi"})

    assert response.status_code == 404


def test_send_message_missing_content():
    client, account = _make_client(CONTACTS)

    response = client.post("/api/v1/messages/zQAliceCompressedKey", json={})

    assert response.status_code == 400
    account.send_message.assert_not_called()


def test_send_message_empty_content():
    client, account = _make_client(CONTACTS)

    response = client.post(
        "/api/v1/messages/zQAliceCompressedKey", json={"content": ""}
    )

    assert response.status_code == 400
    account.send_message.assert_not_called()


def test_send_message_too_long():
    client, account = _make_client(CONTACTS)

    response = client.post(
        "/api/v1/messages/zQAliceCompressedKey",
        json={"content": "x" * 2001},
    )

    assert response.status_code == 400
    account.send_message.assert_not_called()


def test_send_message_embeds_only():
    client, account = _make_client(CONTACTS)

    embeds = [
        {
            "author": {"name": "Alert"},
            "title": "Server down",
            "description": "prod-east-1 is unreachable",
            "fields": [{"name": "Severity", "value": "critical"}],
            "footer": {"text": "monitoring-bot"},
        }
    ]
    response = client.post(
        "/api/v1/messages/zQAliceCompressedKey", json={"embeds": embeds}
    )

    assert response.status_code == 201
    assert response.json() == {"status": "ok"}
    account.send_message.assert_called_once()
    sent_text = account.send_message.call_args[0][1]
    assert "Alert" in sent_text
    assert "Server down" in sent_text
    assert "prod-east-1 is unreachable" in sent_text
    assert "Severity: critical" in sent_text
    assert "monitoring-bot" in sent_text


def test_send_message_content_takes_precedence_over_embeds():
    client, account = _make_client(CONTACTS)

    client.post(
        "/api/v1/messages/zQAliceCompressedKey",
        json={"content": "plain text", "embeds": [{"title": "ignored"}]},
    )

    account.send_message.assert_called_once_with("0xalice", "plain text")


def test_send_message_backend_error():
    client, account = _make_client(CONTACTS)
    account.send_message.side_effect = SendContentError("boom")

    response = client.post(
        "/api/v1/messages/zQAliceCompressedKey", json={"content": "hi"}
    )

    assert response.status_code == 502
