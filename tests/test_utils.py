import hmac
from hashlib import sha256

from status_bot.modules import utils


def test_hmac_is_deterministic():
    first = utils.to_hmac_sha256_hash("hello", "test-pepper")
    second = utils.to_hmac_sha256_hash("hello", "test-pepper")
    expected = hmac.new(b"test-pepper", b"hello", sha256).hexdigest()
    assert first == second == expected


def test_hmac_differs_from_plain_sha256():
    assert utils.to_hmac_sha256_hash("hello", "test-pepper") != utils.to_sha256_hash("hello")


def test_hmac_differs_across_peppers():
    assert utils.to_hmac_sha256_hash("hello", "pepper-a") != utils.to_hmac_sha256_hash(
        "hello", "pepper-b"
    )


def test_hmac_with_salt_differs_from_unsalted():
    assert (
        utils.to_hmac_sha256_hash("hello", "test-pepper", salt="abc")
        != utils.to_hmac_sha256_hash("hello", "test-pepper")
    )


def test_hmac_with_salt_is_deterministic():
    first = utils.to_hmac_sha256_hash("hello", "test-pepper", salt="abc")
    second = utils.to_hmac_sha256_hash("hello", "test-pepper", salt="abc")
    assert first == second


def test_hmac_differs_across_salts():
    assert utils.to_hmac_sha256_hash(
        "hello", "test-pepper", salt="abc"
    ) != utils.to_hmac_sha256_hash("hello", "test-pepper", salt="def")


def test_generate_salt_returns_unique_hex():
    salts = {utils.generate_salt() for _ in range(100)}
    assert len(salts) == 100
    assert all(len(s) == 32 for s in salts)


def test_fallback_to_plain_sha256_when_no_pepper(monkeypatch):
    monkeypatch.setattr(utils, "_PEPPER_WARNED", False)
    assert (
        utils.to_hmac_sha256_hash("hello", "")
        == utils.to_sha256_hash("hello")
        == sha256(b"hello").hexdigest()
    )