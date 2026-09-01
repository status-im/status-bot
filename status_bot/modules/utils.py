import datetime
import hmac
import logging
import os
import pickle
import re
from hashlib import sha256
import json
import pandas as pd
from typing import Any
import requests

from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from status_bot.exceptions import ImageDownloadFailedException
from status_bot.models import ContactRequest

logger = logging.getLogger(__name__)

_PEPPER_WARNED = False


def camel_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def to_sha256_hash(value: str) -> str:
    return sha256(value.encode()).hexdigest()

def remove_public_key(text: str) -> str:
    """
    Remove any `@public-key` patterns from text message
    """
    pattern = re.compile(r"(?<![\w.])@0x[0-9a-fA-F]{130}")
    return pattern.sub("@anon", text)

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


def extract_contact_request(event: dict, new_user_message: str) -> ContactRequest:
    body = event.get('body')
    if body is None:
        raise ValueError("Missing Body from the ContactRequest")
    contact_event = body.get("contact")
    if contact_event is None:
        raise ValueError("Missing contact part from the ContactRequest")
    return ContactRequest(
            id=body.get("message").get("id"),
            public_key=contact_event.get("id"),
            request_message=event.get("message"),
            request_timestamp=datetime.datetime.fromtimestamp(
                event.get("timestamp", 0) / 1_000
            ),
            conversation_id=event.get("conversationId"),
            is_new_user=event.get("message") == new_user_message
        )

def download_image(url: str, image_path):
    session = requests.Session()
    session.trust_env = False  # Avoid proxy conflicts

    # Configure retry logic for transient 503 errors
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    try:
        logger.info(f"Image URL {url}")
        response = session.get(url, verify=False, stream=True, timeout=10)
        logger.debug("Starting the download")
        with open(image_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        logger.debug(f"Image successfully downloaded to {image_path}")

        response.raise_for_status()  # Raise an exception for HTTP errors
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading image: {e}")
        raise ImageDownloadFailedException(f"Failed to download image from {url}")

