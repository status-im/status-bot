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

_MESSAGE_ENCRYPTED_COLUMNS = [
    "id",
    "from",
    "response_to",
    "chat_id",
    "text",
]
