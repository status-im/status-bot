import os
import yaml
from dotenv import load_dotenv as __load_dotenv

CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "accounts")
UPLOAD_PATH = os.path.join(os.path.join(os.path.dirname(__file__), "uploads"))

with open(os.path.join(os.path.dirname(__file__), "config.yaml"), "r") as f:
    CONFIG: dict = yaml.safe_load(f)

__load_dotenv()

STATUS_BACKEND_PARAMS = {
    **CONFIG["status_app"]["backend_params"],
    "url": f"http:{'s' if CONFIG['status_app']['url']['is_https']  else ''}//{os.environ.get('STATUS_BACKEND_BASE_URL', 'localhost')}:{CONFIG['status_app']['url']['port']}"
}
