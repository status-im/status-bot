import datetime
import hmac
import logging
import os
import pickle
import re
from hashlib import sha256

import pandas as pd
from typing import Any

from status_bot.models import ContactRequest

logger = logging.getLogger(__name__)

_PEPPER_WARNED = False


def camel_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def to_sha256_hash(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def to_hmac_sha256_hash(value: str, pepper: str = "") -> str:
    global _PEPPER_WARNED
    if pepper:
        return hmac.new(pepper.encode(), value.encode(), sha256).hexdigest()
    if not _PEPPER_WARNED:
        _PEPPER_WARNED = True
        logger.warning(
            "bot.bot_hash_pepper is not set, falling back to plain SHA-256 "
            "hashing (content is not protected against dictionary attacks)"
        )
    return to_sha256_hash(value)


def to_midnight(timestamp: datetime.datetime) -> datetime.datetime:
    return timestamp.replace(minute=0, second=0, hour=0, microsecond=0)


def save_file(file_path: str, data: Any):
    folder = os.path.dirname(file_path)
    if len(folder) > 0:
        os.makedirs(folder, exist_ok=True)

    if isinstance(data, pd.DataFrame):
        data.to_csv(file_path, index=False)
        return

    with open(file_path, "wb") as f:
        pickle.dump(data, f)


def extract_contact_request(event: dict) -> ContactRequest:
    body = event.get('body')
    if body is None:
        raise ValueError("Missing Body from the ContactRequest")
    contact_event = body.get("contact")
    if contact_event is None:
        raise ValueError("Missing contact part from the ContactRequest")
    return ContactRequest(
            id=body.get("id"),
            public_key=contact_event.get("id"),
            contact_name=contact_event.get("name"),
            request_message=event.get("message"),
            request_timestamp=event.get("timestamp", 0),
            conversation_id=event.get("conversationId")
        )

