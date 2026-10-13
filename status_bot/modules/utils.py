import base64
import binascii
import datetime
import logging
import re
from hashlib import sha256
from typing import Optional
import requests

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import PBKDF2
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from status_bot.exceptions import ImageDownloadFailedException
from status_sdk.types import Chat

logger = logging.getLogger(__name__)

_EMPTY_KEY_WARNED = False

# AES-SIV accepts 32, 48 or 64 byte keys (two keys of 16/24/32 bytes)
_SIV_KEY_LENGTHS = (32, 48, 64)
_PBKDF2_SALT = b"status-bot-receiver-v1"
_PBKDF2_ITERATIONS = 200_000

# Prefix marking a column value as an encrypted blob ("enc1" = format version 1).
# Legacy values written as plain HMAC-SHA256 hex digests do not carry it.
ENCRYPTION_PREFIX = "enc1$"


def to_sha256_hash(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def remove_public_key(text: str) -> str:
    """
    Remove any `@public-key` patterns from text message
    """
    pattern = re.compile(r"(?<![\w.])@0x[0-9a-fA-F]{130}")
    return pattern.sub("@anon", text)


def _decode_raw_key(secret: str) -> Optional[bytes]:
    """
    Decode a hex or base64 encoded AES-SIV key.

    Returns `None` when the secret is not an encoded key of a valid length,
    in which case it is treated as a passphrase (see `derive_encryption_key`).
    """
    decoders = (
        lambda value: bytes.fromhex(value),
        lambda value: base64.b64decode(value, validate=True),
        lambda value: base64.urlsafe_b64decode(value),
    )
    for decoder in decoders:
        try:
            raw = decoder(secret)
        except (ValueError, binascii.Error):
            continue
        if len(raw) in _SIV_KEY_LENGTHS:
            return raw
    return None


def derive_encryption_key(secret: str) -> bytes:
    """
    Derive the AES-SIV key used to encrypt stored messages from `bot.encryption_key`.

    A hex or base64 encoded 32/48/64 byte value is used as the key directly,
    any other value is stretched with PBKDF2-HMAC-SHA256.

    An empty secret still yields a key (so persistence keeps working and dedup
    stays stable), but a warning is logged: the stored values are then only
    obfuscated and recoverable by anyone with access to the database.
    """
    global _EMPTY_KEY_WARNED
    if not secret and not _EMPTY_KEY_WARNED:
        _EMPTY_KEY_WARNED = True
        logger.warning(
            "bot.encryption_key is not set, deriving the encryption key from an "
            "empty secret (stored messages are NOT protected)"
        )
    raw = _decode_raw_key(secret) if secret else None
    if raw is not None:
        return raw
    return PBKDF2(
        secret.encode(),
        _PBKDF2_SALT,
        dkLen=64,
        count=_PBKDF2_ITERATIONS,
        hmac_hash_module=SHA256,
    )


def to_encrypted_value(value: str, key: bytes) -> str:
    """
    Encrypt a string with AES-SIV (deterministic, authenticated).

    Deterministic means the same plaintext always yields the same ciphertext,
    which keeps primary-key dedup working on encrypted identifiers.
    The result is `ENCRYPTION_PREFIX` + urlsafe base64(synthetic IV + ciphertext).
    """
    cipher = AES.new(key, AES.MODE_SIV)
    ciphertext, mac = cipher.encrypt_and_digest(value.encode())
    blob = base64.urlsafe_b64encode(mac + ciphertext).decode()
    return ENCRYPTION_PREFIX + blob


def from_encrypted_value(value: str, key: bytes) -> str:
    """
    Decrypt a value produced by `to_encrypted_value`.

    Raises `ValueError` when the value is not an encrypted blob of this format
    or when it was tampered with / encrypted with another key.
    """
    if not value.startswith(ENCRYPTION_PREFIX):
        raise ValueError(f"Value is not an encrypted blob: {value[:32]!r}...")
    blob = base64.urlsafe_b64decode(value[len(ENCRYPTION_PREFIX) :])
    mac, ciphertext = blob[:16], blob[16:]
    cipher = AES.new(key, AES.MODE_SIV)
    return cipher.decrypt_and_verify(ciphertext, mac).decode()


def to_midnight(timestamp: datetime.datetime) -> datetime.datetime:
    return timestamp.replace(minute=0, second=0, hour=0, microsecond=0)


def download_image(url: str, image_path: str):
    session = requests.Session()
    session.trust_env = False  # Avoid proxy conflicts

    # Configure retry logic for transient 503 errors
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    try:
        logger.debug(f"Image URL {url}")
        response = session.get(url, verify=False, stream=True, timeout=10)
        logger.debug("Starting the download")
        with open(image_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                else:
                    logger.info("No chunk")
        logger.debug(f"Image successfully downloaded to {image_path}")

        response.raise_for_status()  # Raise an exception for HTTP errors
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading image: {e}")
        raise ImageDownloadFailedException(f"Failed to download image from {url}")


def is_group_chat_message(message, chat_id: Optional[str] = None) -> bool:
    """
    Determind if the message is from a group chat
    Parameters:
        - event_data: entire event data
        - chat_id: Optional id of a chat to compare
    Output:
        - boolean indiciating if the message is from a ChatGroup and if it has the same chat_id
    """
    if message.chat_type != Chat.GROUP:
        return False
    if not chat_id:
        return True
    if message.chat_id == chat_id:
        return True
    return False
