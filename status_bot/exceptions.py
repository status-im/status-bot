from typing import Optional

class ImageDownloadFailedException(Exception):
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "The image download failed")
