from typing import Optional


class MandatoryModuleParameterMissingException(Exception):
    def __init__(
        self, msg: str = "Missing Field in the module config", missing_fields: list[str] = []
    ):
        super().__init__(f"{msg}: {', '.join(missing_fields)}")


class ImageDownloadFailedException(Exception):
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "The image download failed")
