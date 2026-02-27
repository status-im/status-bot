"""
Function that simplify the Status Backend data extraction process
"""
from clients.status_backend import StatusBackend
import os, json, datetime, json
import constants

def login(backend: StatusBackend, username: str, is_chat: bool = True) -> dict:
    """
    Login to Status Backend with the given username.
    NOTE: Account must already exist!

    Parameters:
        - `backend` - the `StatusBackend`
        - `username` - the username of the account
        - `is_chat` - if `True` then Logos Messaging will be launched

    Output:
        - the account information
    """
    file_path = os.path.join(constants.CREDENTIALS_PATH, f"{username}.json")
    if not os.path.exists(file_path):
        raise Exception(f"Please make sure you create an account with file 'create_account.py' before running this file")

    with open(file_path, "r", encoding="utf-8") as f:
        account_info: dict = json.load(f)

    params = {
        "key_uid": account_info["event"]["account"]["key-uid"],
        "password": account_info["credentials"]["password"]
    }
    backend.initialize()
    backend.login(**params)
    backend.wait_for_login()

    if is_chat:
        backend.wakuext_service.start_messenger()

    output = {
        "account_name": account_info["event"]["account"]["name"],
        "account_key_uid": params["key_uid"],
        "account_key": account_info["event"]["settings"]["compressedKey"]
    }
    return output



def get_community_info(backend: StatusBackend, url: str) -> dict:
    """
    Get community information for the given URL. 
    
    **Note**: This function will not work if the URL is to a specific channel in a community.

    Parameters:
        - `backend` - the `StatusBackend`
        - `url` - the URL of the community

    Output:
        - community and channel information
    """
    response = backend.sharedurls_service.parse_shared_url(url)
    community_info: dict = backend.wakuext_service.fetch_community(response["community"]["communityId"])
    if not community_info:
        raise Exception(f"No community info found for {url}")

    to_datetime = lambda key: datetime.datetime.fromtimestamp(community_info[key]) if key in community_info else None
    extract_timestamp = datetime.datetime.now()
    data = {
        "community_id": community_info["id"],
        "community_name": community_info["name"],
        "url": url,
        "verified": community_info["verified"],
        "description": community_info["description"],
        "dialog": community_info["introMessage"],
        "leaving_message": community_info["outroMessage"],
        "tags": community_info["tags"],
        "is_member": community_info["isMember"],
        "joined_timestamp": to_datetime("joinedAt"),
        "requested_timestamp": to_datetime("requestedToJoinAt"),
        "encrypted": community_info["encrypted"],
        "members": {
            "total": len(community_info["members"].keys()),
            "info": [
                {
                    "member_id": member_id, 
                    "last_checked": datetime.datetime.fromtimestamp(info["last_update_clock"]) if "last_update_clock" in info else None,
                    "extract_timestamp": extract_timestamp
                } 
                for member_id, info in community_info["members"].items()
            ]
        },
        "channels": [
            {
                "community_id": community_info["id"],
                "channel_id": chat_info["id"],
                "chat_id": community_info["id"] + chat_info["id"],
                "category_id": chat_info["categoryID"] if len(chat_info["categoryID"]) > 0 else None,
                "channel_name": chat_info["name"], 
                "description": chat_info["description"],
            }
            for chat_info in list(community_info["chats"].values())
        ]
    }

    return data


def get_contacts(backend: StatusBackend) -> list[dict]:
    """
    Get all of the contacts that the bot has.
    NOTE: You have to be logged in to Status app already!

    Parameters:
        - `backend` - the `StatusBackend`

    Output:
        - the contacts that the bot has
    """
    info = [
        {
            "id": user["id"],
            "name": user["displayName"] if len(user["displayName"]) > 0 else None,
            "chat_key": user["compressedKey"],
            "emojis": "; ".join(user["emojiHash"])
        }
        for user in backend.wakuext_service.get_contacts()
    ]
    return info



def save_messages(backend: StatusBackend, chat_id: str, folder: str, community_info: dict, pagination: int = 100, batch_size: int = 10):
    """
    Get all of the mesages from a chat.
    NOTE: You have to be logged in to Status app already!

    Params:
        - `chat_id` - the chat id that will be scraped
        - `folder` - where the batched data will be saved
        - `pagination` - how many results to get per `.chat_messages` call
        - `batch_size` - the number of messages that will be turned into a batch
    """
    def save_batch(messages: list[str], folder: str):
        timestamp = datetime.datetime.now().timestamp()

        file_path = os.path.join(folder, str(datetime.datetime.now().timestamp()).replace(".", "") + ".json")
        data = {
            "metadata": {
                "file_path": file_path,
                "created_at": timestamp,
                "total_messages": len(messages),
                "earliest_msg_timestamp": min(messages, key=lambda d: d["sent_timestamp"])["sent_timestamp"],
                "latest_msg_timestamp": max(messages, key=lambda d: d["sent_timestamp"])["sent_timestamp"],
            },
            "messages": messages,
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    os.makedirs(folder, exist_ok=True)
    messages = []
    cursor = None
    mappings = {
        "id": "message_id",
        "chatId": "channel_id",
        "timestamp": "sent_timestamp",
        "compressedKey": "from_key",
        "emojiHash": "from_emojis",
        "parsedText": "parsed_text",
        "text": "markdown_text",
        "editedAt": "edited_timestamp",
        "links": "links"
    }
    finished = False
    while not finished:
        params = {
            "chat_id": chat_id,
            "limit": pagination
        }
        if cursor:
            params["cursor"] = cursor
        
        chat: dict = backend.wakuext_service.chat_messages(**params)

        messages += [
            {
                "community_id": community_info["community_id"],
                "channel_id": community_info["channel_id"],
                "chat_id": community_info["chat_id"],
                "channel_category_id": community_info["category_id"],
                **{target_key: msg[msg_key] for msg_key, target_key in mappings.items() if msg_key in msg},
                "extracted_at": datetime.datetime.now().timestamp()
            }
            for msg in chat["messages"]
        ]
        if len(chat["cursor"]) > 0:
            cursor: str = chat["cursor"]

        finished = len(chat["cursor"]) == 0
        
        if len(messages) >= batch_size:
            save_batch(messages, folder)
            messages = []
        
    
    if messages:
        save_batch(messages, folder)