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


def test_fallback_to_plain_sha256_when_no_pepper(monkeypatch):
    monkeypatch.setattr(utils, "_PEPPER_WARNED", False)
    assert (
        utils.to_hmac_sha256_hash("hello", "")
        == utils.to_sha256_hash("hello")
        == sha256(b"hello").hexdigest()
    )