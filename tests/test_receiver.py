import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from status_bot.database import Database
from status_bot.models.message import ReceivedMessage
from status_bot.modules import receiver
from status_bot.modules.base import ModuleConfig, ModuleContext
from status_bot.modules.utils import (
    ENCRYPTION_PREFIX,
    derive_encryption_key,
    from_encrypted_value,
)

from status_sdk import types
from status_sdk.models import Message

KEY = derive_encryption_key("test-secret")
OTHER_KEY = derive_encryption_key("other-secret")


def _message(**overrides) -> Message:
    params = {
        "id": "msg-1",
        "chat_id": "chat-1",
        "content": "hello world",
        "content_type": types.Content.TEXT,
        "from_public_key": "0xuser",
        "timestamp": datetime.datetime.fromtimestamp(1700000000),
        "chat_type": types.Chat.PRIVATE,
        "source": "status",
    }
    params.update(overrides)
    return Message(**params)


def _receiver_module(db, secret="test-secret") -> receiver.ReceiverModule:
    config = SimpleNamespace(bot=SimpleNamespace(encryption_key=secret))
    ctx = ModuleContext(
        account=None,
        config=ModuleConfig(name="receiver", settings={}),
        db=db,
        shared_state={"config": config},
    )
    module = receiver.ReceiverModule(ctx)
    module.start()
    return module


def _stored_messages(db):
    with db.session() as session:
        return session.execute(select(ReceivedMessage)).scalars().all()


def test_build_message_row_encrypts_content_and_identifiers():
    row = receiver.build_message_row(_message(), KEY)

    assert from_encrypted_value(row.text, KEY) == "hello world"
    assert from_encrypted_value(row.id, KEY) == "msg-1"
    assert from_encrypted_value(row.chat_id, KEY) == "chat-1"
    assert from_encrypted_value(row.from_, KEY) == "0xuser"


def test_build_message_row_encrypts_reply_id():
    row = receiver.build_message_row(_message(reply_id="msg-0"), KEY)
    assert from_encrypted_value(row.response_to, KEY) == "msg-0"


def test_build_message_row_encryption_is_deterministic():
    first = receiver.build_message_row(_message(), KEY)
    second = receiver.build_message_row(_message(), KEY)

    # Same plaintext -> same ciphertext, so primary-key dedup keeps working
    assert first.id == second.id
    assert first.text == second.text
    assert first.chat_id == second.chat_id


def test_build_message_row_encryption_differs_across_keys():
    row = receiver.build_message_row(_message(), KEY)
    other = receiver.build_message_row(_message(), OTHER_KEY)

    assert row.text != other.text
    with pytest.raises(ValueError):
        from_encrypted_value(row.text, OTHER_KEY)


def test_build_message_row_encrypted_columns_follow_constants():
    row = receiver.build_message_row(_message(reply_id="msg-0"), KEY)

    for column in receiver._MESSAGE_ENCRYPTED_COLUMNS:
        attribute = receiver._COLUMN_TO_ATTRIBUTE[column]
        value = getattr(row, attribute)
        assert value.startswith(ENCRYPTION_PREFIX), column

    # No plaintext leaks in the persisted row
    assert "hello world" not in str(row.__dict__.values())
    assert "0xuser" not in str(row.__dict__.values())


def test_build_message_row_content_type_enum_stored_as_int():
    row = receiver.build_message_row(_message(content_type=types.Content.IMAGE), KEY)
    assert row.content_type == types.Content.IMAGE.value


def test_build_message_row_raw_int_content_type_preserved():
    # content types without an enum branch in the SDK stay raw ints
    row = receiver.build_message_row(_message(content_type=11), KEY)
    assert row.content_type == 11


def test_build_message_row_chat_type_stored_as_enum_name():
    row = receiver.build_message_row(_message(chat_type=types.Chat.GROUP), KEY)
    assert row.message_type == "GROUP"


def test_build_message_row_none_reply_id_stored_as_null():
    row = receiver.build_message_row(_message(reply_id=None), KEY)
    assert row.response_to is None


def test_build_message_row_timestamps():
    timestamp = datetime.datetime.fromtimestamp(1700000000)
    row = receiver.build_message_row(_message(timestamp=timestamp), KEY)

    assert row.whisper_timestamp == timestamp
    assert isinstance(row.received_timestamp, datetime.datetime)
    assert row.received_timestamp <= datetime.datetime.now()


def test_build_message_row_columns_without_message_field_stay_null():
    row = receiver.build_message_row(_message(), KEY)

    assert row.alias is None
    assert row.contact_request_state is None
    assert row.compressed_key is None


def test_on_event_persists_encrypted_row():
    db = Database("sqlite", host="", port=0, user="", password="", name=":memory:")
    db.create_tables()
    module = _receiver_module(db)

    module.on_event(_message())

    messages = _stored_messages(db)
    assert len(messages) == 1
    message = messages[0]
    assert from_encrypted_value(message.text, KEY) == "hello world"
    assert from_encrypted_value(message.chat_id, KEY) == "chat-1"
    assert message.content_type == types.Content.TEXT.value
    assert message.message_type == "PRIVATE"
    assert isinstance(message.received_timestamp, datetime.datetime)


def test_on_event_skips_duplicate_ids():
    db = Database("sqlite", host="", port=0, user="", password="", name=":memory:")
    db.create_tables()
    module = _receiver_module(db)

    module.on_event(_message())
    module.on_event(_message())

    assert len(_stored_messages(db)) == 1


def test_on_event_without_database_is_disabled():
    module = _receiver_module(None)

    module.on_event(_message())  # must not raise


def test_on_event_with_empty_key_still_persists():
    db = Database("sqlite", host="", port=0, user="", password="", name=":memory:")
    db.create_tables()
    module = _receiver_module(db, secret="")  # fail open: warn and still persist

    module.on_event(_message())

    messages = _stored_messages(db)
    assert len(messages) == 1
    assert messages[0].text.startswith(ENCRYPTION_PREFIX)


def test_on_event_with_message_parsed_by_sdk():
    # Same path as the event stream: raw status-go payload -> Message.from_raw
    raw = {
        "id": "0ximage-msg",
        "chatId": "chat-1",
        "from": "0xuser",
        "whisperTimestamp": 1700000000000,
        "messageType": 1,
        "contentType": 7,
        "text": "a caption",
        "responseTo": "",
        "image": ["http://localhost:9000/messageId=abc"],
        "albumId": "",
        "albumImagesCount": 0,
    }
    message = Message.from_raw(raw)

    db = Database("sqlite", host="", port=0, user="", password="", name=":memory:")
    db.create_tables()
    module = _receiver_module(db)

    module.on_event(message)

    stored = _stored_messages(db)
    assert len(stored) == 1
    row = stored[0]
    assert row.content_type == types.Content.IMAGE.value
    assert row.message_type == "PRIVATE"
    assert row.response_to is None
    decrypted = from_encrypted_value(row.text, KEY)
    assert "a caption" in decrypted
    assert "http://localhost:9000/messageId=abc" in decrypted
    assert row.whisper_timestamp == datetime.datetime.fromtimestamp(1700000000)
