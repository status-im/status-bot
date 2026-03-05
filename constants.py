import os
import yaml
from dotenv import load_dotenv as __load_dotenv

CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "accounts")
UPLOAD_PATH = os.path.join(os.path.join(os.path.dirname(__file__), "uploads"))

with open(os.path.join(os.path.dirname(__file__), "config.yaml"), "r") as f:
    CONFIG: dict = yaml.safe_load(f)

__load_dotenv()

# Make bot_name optional in config.yaml
# You can use .env STATUS_USERNAME as an alternative
__bot_name = CONFIG["status_app"].get("bot_name")
if not __bot_name:
    __bot_name = ""

if len(__bot_name) == 0 and os.environ.get("STATUS_USERNAME"):
    CONFIG["status_app"]["bot_name"] = os.environ.get("STATUS_USERNAME")

STATUS_BACKEND_PARAMS = {
    **CONFIG["status_app"]["backend_params"],
    "url": f"http:{'s' if CONFIG['status_app']['url']['is_https']  else ''}//{os.environ.get('STATUS_BACKEND_BASE_URL', 'localhost')}:{CONFIG['status_app']['url']['port']}"
}
