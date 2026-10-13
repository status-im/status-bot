import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from status_bot.database import Database
from status_bot.models.message import ReceivedMessage


def _database() -> Database:
    db = Database("sqlite", host="", port=0, user="", password="", name=":memory:")
    db.create_tables()
    return db


def test_insert_and_read_back_via_orm():
    db = _database()
    with db.session() as session:
        session.add(
            ReceivedMessage(
                id="msg-1",
                whisper_timestamp=datetime.datetime(2024, 1, 1, 12, 0, 0),
                from_="0xuser",
                alias="Ali",
                text="hello world",
                chat_id="chat-1",
                response_to="msg-0",
                content_type=1,
                message_type="PRIVATE",
                contact_request_state=2,
                compressed_key="zQ3...",
                received_timestamp=datetime.datetime(2024, 1, 1, 12, 0, 0),
            )
        )
        session.commit()

    with db.session() as session:
        messages = session.execute(select(ReceivedMessage)).scalars().all()

    assert len(messages) == 1
    message = messages[0]
    assert message.id == "msg-1"
    assert message.whisper_timestamp == datetime.datetime(2024, 1, 1, 12, 0, 0)
    assert message.from_ == "0xuser"
    assert message.alias == "Ali"
    assert message.text == "hello world"
    assert message.chat_id == "chat-1"
    assert message.response_to == "msg-0"
    assert message.content_type == 1
    assert message.message_type == "PRIVATE"
    assert message.contact_request_state == 2
    assert message.compressed_key == "zQ3..."
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


def test_create_tables_is_idempotent():
    db = _database()
    db.create_tables()
    db.create_tables()
