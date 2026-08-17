import datetime

import pandas as pd
from sqlalchemy import select

from status_bot.database import Database
from status_bot.models.chat import ReceivedChat
from status_bot.models.message import ReceivedMessage


def _database() -> Database:
    db = Database("sqlite", host="", port=0, user="", password="", name=":memory:", schema="public")
    db.init_tables()
    return db


def _message_row() -> dict:
    return {
        "id": "msg-1",
        "whisper_timestamp": 1700000000000,
        "from": "0xuser",
        "alias": "Ali",
        "seen": True,
        "rtl": False,
        "line_count": 2,
        "text": "hello world",
        "chat_id": "chat-1",
        "local_chat_id": "local-chat-1",
        "clock": 123,
        "replace": "",
        "response_to": "msg-0",
        "ens_name": "alice.eth",
        "display_name": "Alice",
        "timestamp": 1700000000000,
        "content_type": 1,
        "message_type": 0,
        "contact_request_state": 0,
        "compressed_key": "0xcompressed",
        "received_timestamp": datetime.datetime(2024, 1, 1, 12, 0, 0),
        "salt": "a" * 32,
    }


def test_insert_and_read_back_via_orm():
    db = _database()
    db.insert(pd.DataFrame([_message_row()]), "received_messages", [])

    with db.session() as session:
        messages = session.execute(select(ReceivedMessage)).scalars().all()

    assert len(messages) == 1
    message = messages[0]
    assert message.id == "msg-1"
    assert message.from_ == "0xuser"
    assert message.text == "hello world"
    assert message.chat_id == "chat-1"
    assert message.local_chat_id == "local-chat-1"
    assert message.ens_name == "alice.eth"
    assert message.display_name == "Alice"
    assert message.line_count == 2
    assert message.seen is True
    assert message.rtl is False
    assert message.salt == "a" * 32
    assert message.received_timestamp == datetime.datetime(2024, 1, 1, 12, 0, 0)


def test_to_pandas_read_back_matches_orm():
    db = _database()
    db.insert(pd.DataFrame([_message_row()]), "received_messages", [])

    data = db.to_pandas("SELECT * FROM received_messages")

    assert len(data) == 1
    assert data["id"].iloc[0] == "msg-1"
    assert data["from"].iloc[0] == "0xuser"
    assert data["chat_id"].iloc[0] == "chat-1"
    assert data["text"].iloc[0] == "hello world"


def test_non_model_columns_are_dropped():
    db = _database()
    row = _message_row()
    row["parsed_text"] = {"body": "hello world"}
    db.insert(pd.DataFrame([row]), "received_messages", [])

    data = db.to_pandas("SELECT * FROM received_messages")

    assert len(data) == 1
    assert "parsed_text" not in data.columns
    assert data["id"].iloc[0] == "msg-1"


def test_ms_timestamps_coerced_to_datetime():
    db = _database()
    db.insert(pd.DataFrame([_message_row()]), "received_messages", [])

    expected = datetime.datetime.fromtimestamp(1700000000000 / 1000)

    with db.session() as session:
        message = session.execute(select(ReceivedMessage)).scalars().one()
        assert isinstance(message.timestamp, datetime.datetime)
        assert isinstance(message.whisper_timestamp, datetime.datetime)
        assert message.timestamp == expected
        assert message.whisper_timestamp == expected


def test_duplicate_primary_key_is_skipped():
    db = _database()
    df = pd.DataFrame([_message_row()])
    db.insert(df, "received_messages", [])
    db.insert(df, "received_messages", [])

    data = db.to_pandas("SELECT * FROM received_messages")

    assert len(data) == 1


def test_chat_round_trip_via_orm():
    db = _database()
    row = {
        "id": "chat-1",
        "type": "public",
        "name": "General",
        "received_timestamp": datetime.datetime(2024, 1, 1, 12, 0, 0),
        "salt": "b" * 32,
    }
    db.insert(pd.DataFrame([row]), "received_chats", [])

    with db.session() as session:
        chats = session.execute(select(ReceivedChat)).scalars().all()

    assert len(chats) == 1
    chat = chats[0]
    assert chat.id == "chat-1"
    assert chat.type == "public"
    assert chat.name == "General"
    assert chat.salt == "b" * 32