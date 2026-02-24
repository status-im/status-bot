import os

CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "accounts")

STATUS_BACKEND_PARAMS = {
    "url": "http://localhost:8080",
    "logLevel": "INFO",
    "data_dir": os.path.join(os.path.dirname(__file__), "data-dir")
}
