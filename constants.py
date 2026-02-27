import os
import yaml

CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "accounts")
UPLOAD_PATH = os.path.join(os.path.join(os.path.dirname(__file__), "uploads"))

with open(os.path.join(os.path.dirname(__file__), "config.yaml"), "r") as f:
    CONFIG: dict = yaml.safe_load(f)

STATUS_BACKEND_PARAMS = CONFIG["status_app"]["backend_params"]