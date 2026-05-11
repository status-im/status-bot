import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from status_bot.database import Database
from status_bot.models.chat import ReceivedChat
from status_bot.models.message import ReceivedMessage


def _database() -> Database:
    db = Database("sqlite", host="", port=0, user="", password="", name=":memory:", schema="public")
    db.create_tables()
    return db


def test_insert_and_read_back_via_orm():
    db = _database()
    with db.session() as session:
        session.add(ReceivedMessage(
            id="msg-1",
            whisper_timestamp=datetime.datetime(2024, 1, 1, 12, 0, 0),
            from_="0xuser",
            alias="Ali",
            seen=True,
            rtl=False,
            line_count=2,
            text="hello world",
            chat_id="chat-1",
            local_chat_id="local-chat-1",
            ens_name="alice.eth",
            display_name="Alice",
            received_timestamp=datetime.datetime(2024, 1, 1, 12, 0, 0),
        ))
        session.commit()

    with db.session() as session:
        messages = session.execute(select(ReceivedMessage)).scalars().all()

    assert len(messages) == 1
    message = messages[0]
    assert message.id == "msg-1"
    assert message.whisper_timestamp == datetime.datetime(2024, 1, 1, 12, 0, 0)
    assert message.from_ == "0xuser"
    assert message.text == "hello world"
    assert message.chat_id == "chat-1"
    assert message.local_chat_id == "local-chat-1"
    assert message.ens_name == "alice.eth"
    assert message.display_name == "Alice"
    assert message.line_count == 2
    assert message.seen is True
    assert message.rtl is False
    assert message.received_timestamp == datetime.datetime(2024, 1, 1, 12, 0, 0)


def test_duplicate_primary_key_raises_integrity_error():
    db = _database()
    with db.session() as session:
        session.add(ReceivedMessage(id="msg-1", text="first"))
        session.commit()

    with db.session() as session:
        session.add(ReceivedMessage(id="msg-1", text="second"))
        try:
            session.commit()
            raise AssertionError("expected IntegrityError")
        except IntegrityError:
            session.rollback()


def test_chat_round_trip_via_orm():
    db = _database()
    with db.session() as session:
        session.add(ReceivedChat(
            id="chat-1",
            type="public",
            name="General",
            received_timestamp=datetime.datetime(2024, 1, 1, 12, 0, 0),
        ))
        session.commit()

    with db.session() as session:
        chats = session.execute(select(ReceivedChat)).scalars().all()

    assert len(chats) == 1
    chat = chats[0]
    assert chat.id == "chat-1"
    assert chat.type == "public"
    assert chat.name == "General"


def test_create_tables_is_idempotent():
    db = _database()
    db.create_tables()
    db.create_tables()