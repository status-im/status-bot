from clients.status_backend import StatusBackend
import constants, data_utils
import os, datetime, pickle

if __name__ == "__main__":

    backend = StatusBackend(**constants.STATUS_BACKEND_PARAMS)
    info = data_utils.login(backend, constants.CONFIG["status_app"]["bot_name"])
    
    message_folder = os.path.join(constants.UPLOAD_PATH, "messages")
    community_folder = os.path.join(constants.UPLOAD_PATH, "channel_info")

    for channel_url in constants.CONFIG["status_app"]["channels"]:
        community = data_utils.get_community_info(backend, channel_url)
        current_community_folder = os.path.join(community_folder, community["community_id"])
        os.makedirs(current_community_folder, exist_ok=True)
        file_path = os.path.join(current_community_folder, str(datetime.datetime.now().timestamp()).replace(".", "") + ".pkl")
        
        with open(file_path, "wb") as f:
            pickle.dump(community, f)

        for channel in community["channels"]:
            params = {
                "backend": backend,
                "chat_id": channel["chat_id"],
                "folder": message_folder,
                "community_info": channel
            }
            data_utils.save_messages(backend, channel["chat_id"], message_folder, channel)

    backend.logout()