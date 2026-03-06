from clients.status_backend import StatusBackend
from typing import Any
import constants, data_utils
import os, datetime, pickle, time, logging

def save_pkl(file_path: str, data: Any):
    """
    Save the given data into a Pickel file

    Parameters:
        - `file_path` - the path where the data will be saved
        - `data` - the data that will be saved
    """
    with open(file_path, "wb") as f:
        pickle.dump(data, f)

def run(logger: logging.Logger):
    backend = StatusBackend(**constants.STATUS_BACKEND_PARAMS)
    info = data_utils.login(backend, constants.CONFIG["status_app"]["bot_name"])
    logger.info(f"Logged in with account {constants.CONFIG['status_app']['bot_name']}")

    message_folder = os.path.join(constants.UPLOAD_PATH, "messages")
    community_folder = os.path.join(constants.UPLOAD_PATH, "channel_info")

    for channel_url in constants.CONFIG["status_app"]["channels"]:
        logger.info(f"Starting {channel_url}")
        community = data_utils.get_community_info(backend, channel_url)
        current_community_folder = os.path.join(community_folder, community["community_id"])
        os.makedirs(current_community_folder, exist_ok=True)
        file_path = os.path.join(current_community_folder, str(datetime.datetime.now().timestamp()).replace(".", "") + ".pkl")
        save_pkl(file_path, community)

        for channel in community["channels"]:
            msg = f"Downloading messages from {community['community_name']} #{channel['channel_name']}"
            logger.info(msg)
            params = {
                "backend": backend,
                "chat_id": channel["chat_id"],
                "folder": message_folder,
                "community_info": channel
            }
            data_utils.save_messages(**params)

    backend.logout()
    logger.info(f"Logged out of {constants.CONFIG['status_app']['bot_name']}")

if __name__ == "__main__":

    logger = data_utils.get_logger("download")
    while True:
        run(logger)
        seconds = 60 * constants.CONFIG["sleep"]["download"]
        logger.info(f"Sleeping for {constants.CONFIG['sleep']['download']} minutes")
        time.sleep(seconds)
