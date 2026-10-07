from enum import Enum
from importlib.metadata import version as _get_version, PackageNotFoundError
from pathlib import Path
import re


def _get_package_version() -> str:
    """Get the package version from installed metadata or pyproject.toml."""
    try:
        return _get_version("status-bot")
    except PackageNotFoundError:
        # Fallback: read from pyproject.toml when running from source
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
            if match:
                return match.group(1)
        return "unknown"


__version__ = _get_package_version()

_MESSAGE_DETERMINISTIC_COLUMNS = [
    "id",
    "from",
    "response_to",
    "chat_id",
    "local_chat_id",
    "display_name",
    "ens_name",
    "alias",
    "text",
]

_MESSAGE_DROP_COLUMNS = [
    "parsed_text",
    "quoted_message",
    "emoji_hash",
    "gap_parameters",
]

_CHAT_DETERMINISTIC_COLUMNS = [
    "id",
    "name",
]


class EventTypeEnum(Enum):
    MESSAGE = "messages.new"
    LOCAL_NOTIFICATION = "local-notifications"


class NotificationCategoryEnum(Enum):
    CONTACT_REQUEST = "contactRequest"
    NEW_MESSAGE = "newMessage"
    GROUP_INVITE = "groupInvite"
    COMMUNITY_REQUEST_TO_JOIN = "communityRequestToJoin"
    COMMUNITY_JOINED = "communityJoined"
