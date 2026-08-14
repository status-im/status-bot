import hmac
from hashlib import sha256

import pandas as pd

from status_bot.modules import receiver


def _hashed(value):
    return hmac.new(b"test-pepper", value.encode(), sha256).hexdigest()


def test_message_columns_hashed_and_jsonb_dropped():
    df = pd.DataFrame(
        [
            {
                "id": "msg-1",
                "from": "0xuser",
                "response_to": "msg-0",
                "display_name": "Alice",
                "ens_name": "alice.eth",
                "alias": "Ali",
                "text": "hello world",
                "chat_id": "chat-1",
                "local_chat_id": "local-chat-1",
                "parsed_text": {"body": "hello world"},
                "quoted_message": {"text": "original"},
                "emoji_hash": ["1f600"],
                "gap_parameters": {"link": "https://example.com"},
            }
        ]
    )
    result = receiver.transform_dataframe(
        df,
        receiver._MESSAGE_DETERMINISTIC_COLUMNS,
        receiver._MESSAGE_SALTED_COLUMNS,
        receiver._MESSAGE_DROP_COLUMNS,
        pepper="test-pepper",
    )

    for col in ["id", "from", "response_to", "chat_id", "local_chat_id"]:
        assert result[col].iloc[0] == _hashed(str(df[col].iloc[0]))

    for col in ["display_name", "ens_name", "alias", "text"]:
        salt = result["salt"].iloc[0]
        expected = hmac.new(
            b"test-pepper", (salt + str(df[col].iloc[0])).encode(), sha256
        ).hexdigest()
        assert result[col].iloc[0] == expected

    assert result["salt"].iloc[0]
    for col in ["parsed_text", "quoted_message", "emoji_hash", "gap_parameters"]:
        assert col not in result.columns


def test_salted_columns_differ_between_rows():
    df = pd.DataFrame(
        [
            {"id": "msg-1", "text": "same phrase"},
            {"id": "msg-2", "text": "same phrase"},
        ]
    )
    result = receiver.transform_dataframe(
        df,
        receiver._MESSAGE_DETERMINISTIC_COLUMNS,
        receiver._MESSAGE_SALTED_COLUMNS,
        [],
        pepper="test-pepper",
    )

    assert result["salt"].iloc[0] != result["salt"].iloc[1]
    assert result["text"].iloc[0] != result["text"].iloc[1]


def test_chat_columns_hashed():
    df = pd.DataFrame([{"id": "chat-1", "name": "General", "type": "public"}])
    result = receiver.transform_dataframe(
        df,
        receiver._CHAT_DETERMINISTIC_COLUMNS,
        receiver._CHAT_SALTED_COLUMNS,
        [],
        pepper="test-pepper",
    )

    assert result["id"].iloc[0] == _hashed("chat-1")
    salt = result["salt"].iloc[0]
    assert result["name"].iloc[0] == hmac.new(
        b"test-pepper", (salt + "General").encode(), sha256
    ).hexdigest()
    assert result["type"].iloc[0] == "public"


def test_unknown_dict_column_dropped_without_raising():
    df = pd.DataFrame([{"id": "msg-1", "text": "hi", "future_field": {"a": 1}}])
    result = receiver.transform_dataframe(
        df,
        receiver._MESSAGE_DETERMINISTIC_COLUMNS,
        receiver._MESSAGE_SALTED_COLUMNS,
        [],
        pepper="test-pepper",
    )

    assert "future_field" not in result.columns
    assert "text" in result.columns


def test_column_names_lowercased():
    df = pd.DataFrame([{"ID": "msg-1", "Text": "hi"}])
    result = receiver.transform_dataframe(
        df, ["id"], ["text"], [], pepper="test-pepper"
    )
    assert {"id", "text", "salt"}.issubset(result.columns)


def test_missing_columns_are_tolerated():
    df = pd.DataFrame([{"id": "msg-1"}])
    result = receiver.transform_dataframe(
        df,
        receiver._MESSAGE_DETERMINISTIC_COLUMNS,
        receiver._MESSAGE_SALTED_COLUMNS,
        [],
        pepper="test-pepper",
    )
    assert result["id"].iloc[0] == _hashed("msg-1")
    assert "salt" not in result.columns or not result["salt"].notna().any()


def test_no_salt_column_when_no_salted_columns():
    df = pd.DataFrame([{"id": "chat-1", "type": "public"}])
    result = receiver.transform_dataframe(
        df, receiver._CHAT_DETERMINISTIC_COLUMNS, [], [], pepper="test-pepper"
    )
    assert "salt" not in result.columns