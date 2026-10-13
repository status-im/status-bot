import pytest

from status_bot.modules import utils


def test_derive_encryption_key_is_deterministic():
    assert utils.derive_encryption_key("secret") == utils.derive_encryption_key("secret")
    assert utils.derive_encryption_key("secret") != utils.derive_encryption_key("other")


def test_derive_encryption_key_from_passphrase_is_64_bytes():
    key = utils.derive_encryption_key("not-an-encoded-key")
    assert len(key) == 64


def test_derive_encryption_key_from_hex_secret():
    secret = "ab" * 32  # 32 bytes as hex
    assert utils.derive_encryption_key(secret) == bytes.fromhex(secret)


def test_derive_encryption_key_from_base64_secret():
    import base64

    raw = bytes(range(32))
    secret = base64.b64encode(raw).decode()
    assert utils.derive_encryption_key(secret) == raw


def test_derive_encryption_key_empty_secret_warns(monkeypatch, caplog):
    monkeypatch.setattr(utils, "_EMPTY_KEY_WARNED", False)
    with caplog.at_level("WARNING"):
        key = utils.derive_encryption_key("")
    assert len(key) == 64
    assert "bot.encryption_key is not set" in caplog.text


def test_derive_encryption_key_empty_secret_warns_once(monkeypatch, caplog):
    monkeypatch.setattr(utils, "_EMPTY_KEY_WARNED", False)
    with caplog.at_level("WARNING"):
        utils.derive_encryption_key("")
        utils.derive_encryption_key("")
    assert caplog.text.count("bot.encryption_key is not set") == 1


def test_encrypt_decrypt_round_trip():
    key = utils.derive_encryption_key("test-secret")
    encrypted = utils.to_encrypted_value("hello world", key)
    assert encrypted.startswith(utils.ENCRYPTION_PREFIX)
    assert "hello world" not in encrypted
    assert utils.from_encrypted_value(encrypted, key) == "hello world"


def test_encryption_is_deterministic():
    key = utils.derive_encryption_key("test-secret")
    assert utils.to_encrypted_value("hello", key) == utils.to_encrypted_value("hello", key)


def test_encryption_differs_across_keys():
    first = utils.to_encrypted_value("hello", utils.derive_encryption_key("key-a"))
    second = utils.to_encrypted_value("hello", utils.derive_encryption_key("key-b"))
    assert first != second


def test_decrypt_with_wrong_key_fails():
    encrypted = utils.to_encrypted_value("hello", utils.derive_encryption_key("key-a"))
    with pytest.raises(ValueError):
        utils.from_encrypted_value(encrypted, utils.derive_encryption_key("key-b"))


def test_decrypt_rejects_tampered_value():
    key = utils.derive_encryption_key("test-secret")
    encrypted = utils.to_encrypted_value("hello", key)
    blob = encrypted[len(utils.ENCRYPTION_PREFIX) :]
    tampered = utils.ENCRYPTION_PREFIX + ("A" if blob[0] != "A" else "B") + blob[1:]
    with pytest.raises(ValueError):
        utils.from_encrypted_value(tampered, key)


def test_decrypt_rejects_legacy_hashed_value():
    key = utils.derive_encryption_key("test-secret")
    legacy = utils.to_sha256_hash("hello")  # pre-encryption format: plain hex digest
    with pytest.raises(ValueError):
        utils.from_encrypted_value(legacy, key)
