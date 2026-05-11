import datetime
import hmac
from hashlib import sha256

from sqlalchemy import select

from status_bot.database import Database
from status_bot.models.chat import ReceivedChat
from status_bot.models.message import ReceivedMessage
from status_bot.modules import receiver
from status_bot.modules.base import ModuleConfig, ModuleContext


def _hashed(value):
    return hmac.new(b"test-pepper", value.encode(), sha256).hexdigest()


def _message_payload():
    return {
        "id": "msg-1",
        "whisper_timestamp": 1700000000000,
        "timestamp": 1700000000000,
        "from": "0xuser",
        "alias": "Ali",
        "seen": True,
        "text": "hello world",
        "chatId": "chat-1",
        "localChatId": "local-chat-1",
        "responseTo": "msg-0",
        "displayName": "Alice",
        "ensName": "alice.eth",
        "parsedText": {"body": "hello world"},
        "quotedMessage": {"text": "original"},
        "emojiHash": ["1f600"],
        "gapParameters": {"link": "https://example.com"},
        "salt": "not-a-model-column",
    }


def test_message_deterministic_fields_hashed_with_pepper():
    rows = receiver.build_model_rows(
        [_message_payload()],
        ReceivedMessage,
        receiver._MESSAGE_DETERMINISTIC_COLUMNS,
        receiver._MESSAGE_DROP_COLUMNS,
        pepper="test-pepper",
    )

    row = rows[0]
    for value, attr in [
        ("msg-1", "id"),
        ("0xuser", "from_"),
        ("msg-0", "response_to"),
        ("chat-1", "chat_id"),
        ("local-chat-1", "local_chat_id"),
        ("Alice", "display_name"),
        ("alice.eth", "ens_name"),
        ("Ali", "alias"),
        ("hello world", "text"),
    ]:
        assert getattr(row, attr) == _hashed(value)

    assert row.seen is True


def test_camel_case_keys_map_to_snake_attributes():
    rows = receiver.build_model_rows(
        [{"chatId": "chat-1", "localChatId": "local-chat-1", "displayName": "Alice"}],
        ReceivedMessage,
        [],
        [],
    )

    row = rows[0]
    assert row.chat_id == "chat-1"
    assert row.local_chat_id == "local-chat-1"
    assert row.display_name == "Alice"


def test_structured_values_skipped_per_row():
    payload = _message_payload()
    payload["message_type"] = [0]
    payload["content_type"] = {"a": 1}

    rows = receiver.build_model_rows([payload], ReceivedMessage, [], [])

    row = rows[0]
    assert row.message_type is None
    assert row.content_type is None


def test_non_model_columns_skipped():
    rows = receiver.build_model_rows([_message_payload()], ReceivedMessage, [], [])

    assert not hasattr(rows[0], "salt")


def test_ms_timestamps_coerced_to_datetime():
    rows = receiver.build_model_rows([_message_payload()], ReceivedMessage, [], [])

    row = rows[0]
    expected = datetime.datetime.fromtimestamp(1700000000000 / 1000)
    assert isinstance(row.timestamp, datetime.datetime)
    assert isinstance(row.whisper_timestamp, datetime.datetime)
    assert row.timestamp == expected
    assert row.whisper_timestamp == expected


def test_drop_columns_removed_before_hashing():
    rows = receiver.build_model_rows(
        [_message_payload()],
        ReceivedMessage,
        receiver._MESSAGE_DETERMINISTIC_COLUMNS,
        ["text"],
        pepper="test-pepper",
    )

    assert rows[0].text is None


def test_none_values_stored_as_null():
    payload = _message_payload()
    payload["display_name"] = None

    rows = receiver.build_model_rows([payload], ReceivedMessage, [], [])

    assert rows[0].display_name is None


def test_empty_pepper_uses_plain_sha256():
    rows = receiver.build_model_rows(
        [_message_payload()],
        ReceivedMessage,
        receiver._MESSAGE_DETERMINISTIC_COLUMNS,
        receiver._MESSAGE_DROP_COLUMNS,
        pepper="",
    )

    assert rows[0].chat_id == sha256("chat-1".encode()).hexdigest()
    assert rows[0].chat_id != _hashed("chat-1")


def test_chat_deterministic_fields_hashed_and_plain_fields_kept():
    rows = receiver.build_model_rows(
        [{"id": "chat-1", "name": "General", "type": "public"}],
        ReceivedChat,
        receiver._CHAT_DETERMINISTIC_COLUMNS,
        [],
        pepper="test-pepper",
    )

    row = rows[0]
    assert row.id == _hashed("chat-1")
    assert row.name == _hashed("General")
    assert row.type == "public"


def _receiver_module(db) -> receiver.ReceiverModule:
    ctx = ModuleContext(
        account=None,
        config=ModuleConfig(name="receiver", settings={}),
        db=db,
        shared_state={},
    )
    module = receiver.ReceiverModule(ctx)
    module.on_start()
    return module


def test_process_and_insert_persists_rows_via_session():
    db = Database("sqlite", host="", port=0, user="", password="", name=":memory:", schema="public")
    db.create_tables()
    module = _receiver_module(db)

    module._process_and_insert(
        [_message_payload()],
        ReceivedMessage,
        receiver._MESSAGE_DETERMINISTIC_COLUMNS,
        receiver._MESSAGE_DROP_COLUMNS,
    )

    with db.session() as session:
        messages = session.execute(select(ReceivedMessage)).scalars().all()

    assert len(messages) == 1
    message = messages[0]
    assert message.chat_id == sha256("chat-1".encode()).hexdigest()
    assert isinstance(message.received_timestamp, datetime.datetime)
    expected = datetime.datetime.fromtimestamp(1700000000000 / 1000)
    assert isinstance(message.timestamp, datetime.datetime)
    assert isinstance(message.whisper_timestamp, datetime.datetime)
    assert message.timestamp == expected
    assert message.whisper_timestamp == expected


def test_process_and_insert_drops_non_model_columns():
    db = Database("sqlite", host="", port=0, user="", password="", name=":memory:", schema="public")
    db.create_tables()
    module = _receiver_module(db)

    module._process_and_insert(
        [_message_payload()],
        ReceivedMessage,
        receiver._MESSAGE_DETERMINISTIC_COLUMNS,
        receiver._MESSAGE_DROP_COLUMNS,
    )

    with db.session() as session:
        messages = session.execute(select(ReceivedMessage)).scalars().all()

    assert len(messages) == 1
    assert not hasattr(messages[0], "salt")


def test_process_and_insert_skips_duplicate_primary_keys():
    db = Database("sqlite", host="", port=0, user="", password="", name=":memory:", schema="public")
    db.create_tables()
    module = _receiver_module(db)

    module._process_and_insert(
        [_message_payload()],
        ReceivedMessage,
        receiver._MESSAGE_DETERMINISTIC_COLUMNS,
        receiver._MESSAGE_DROP_COLUMNS,
    )
    module._process_and_insert(
        [_message_payload()],
        ReceivedMessage,
        receiver._MESSAGE_DETERMINISTIC_COLUMNS,
        receiver._MESSAGE_DROP_COLUMNS,
    )

    with db.session() as session:
        messages = session.execute(select(ReceivedMessage)).scalars().all()

    assert len(messages) == 1