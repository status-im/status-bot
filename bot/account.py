from typing import Optional, Union, Generator, Any
import requests, datetime, re, logging, os
from .signal import Signal
from .logger import Logger
class Account:

    # Enum mappings from original wakuext.py
    __mappings = {
        "contact_request": {
            0: "none",     # No action taken / no association - initial state
            1: "mutual",   # Friends
            2: "sent",     # Request sent from the bot
            3: "received", # Request sent from another account
            4: "dismissed" # Request cancelled
        }
    }
    __prefix_mapping = {
        "messaging": "wakuext",
        "urls": "sharedurls"
    }
    def __init__(self, domain: str = "localhost", port: int = 8080, is_secure: bool = False):
        """
        Work with your own Status App account

        Parameters:
            - `domain` - the domain name where Status Backend is running. If running locally it would be `localhost` and if it's running in a container it would be the image's name.
            - `port` - the port to connect to Status Backend. Verify the port in the Docker files.
            - `is_secure` - if `http` or `https` should be used
        """
        # Path of the account data in the Docker container for Status Backend
        self.__docker_data_folder = "./data-dir"
        # Path of the backups in the Docker container for Status Backend
        self.__docker_backup_folder = "./root/.config/Status/backups"
        # As the docker-compose.yaml folder is at the moment
        # NOTE: This might change for initial release
        self.__backup_local_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backups")
        os.makedirs(self.__backup_local_folder, exist_ok=True)
        self.__logger = Logger()
        self.__timestamp_divisor = 1_000
        self.__kd_iterations = 256000
        self.__is_messenger_launched = False
        # Information for the logged in account
        self.__info = {}
        self.http_base_url = f"http{'s' if is_secure else ''}://{domain}:{port}/statusgo/"
        self.ws_base_url = f"ws://{domain}:{port}/"
        self.urls = {
            "http": {
                "initialize": f"{self.http_base_url}InitializeApplication",
                "login": f"{self.http_base_url}LoginAccount",
                "create": f"{self.http_base_url}CreateAccountAndLogin",
                "restore": f"{self.http_base_url}RestoreAccountAndLogin",
                "logout": f"{self.http_base_url}Logout",
                "create_backup": f"{self.http_base_url}PerformLocalBackup",
                "load_backup": f"{self.http_base_url}LoadLocalBackup",
                "rpc": f"{self.http_base_url}CallRPC",
            },
            "socket": {
                "signals": f"{self.ws_base_url}signals"
            }
        }
        self.__signal = Signal(self.urls["socket"]["signals"])
        # Initialize profile
        self.available_accounts
        # In case if there is a hanging logged in session
        self.logout()

    def login(self, password: str, key_uid: Optional[str] = None, display_name: Optional[str] = None, mnemonic: Optional[str] = None):
        """
        Login to the given account. If it does not exist,
        it will be created and automatically logged in.

        Parameters:
            - `password` - your Status password
            - `key_uid` - your key unique identifier. If not provided `display_name` will be used to fetch it. This means that each `display_name` can be linked to one `key_uid`
            - `display_name` - your Status display name. Use `display_name` and `password` parameter combination if you have a 1 to 1 mapping (each display name has a unique `key_uid`)
            - `mnemonic` - the mnemonic when creating an account. Use this field with `password` and `display_name` to recover an account
        """
        if not key_uid and not display_name:
            raise ValueError("Please provide either a Key Unique Identifier (key_uid) or a Display Name (display_name)...")

        available_accounts = self.available_accounts
        # Login combination: display_name + password
        if not key_uid:
            for account in available_accounts:
                if account["display_name"] != display_name:
                    continue

                key_uid = account["key_uid"]
                break
        # Login combination: key_uid + password
        else:
            available_key_uids = [current["key_uid"] for current in available_accounts]
            if key_uid not in available_key_uids:
                info = "\n".join([f"{current['key_uid']} - {current['display_name']}" for current in self.__available_accounts])
                raise ValueError(f"Given Key Unique Identifier is invalid...\nAvailable Key Unique Identifiers:\n{info}")

        is_new_account = isinstance(key_uid, type(None))
        is_recovery = not isinstance(mnemonic, type(None)) and not key_uid

        url_key = "login"
        params = {
            "keyUid": key_uid,
            "password": password,
            'kdfIterations': self.__kd_iterations
        }

        if is_new_account or is_recovery:
            self.__validate_display_name(display_name)
            params = {
                "rootDataDir": self.__docker_data_folder,
                "kdfIterations": self.__kd_iterations,
                "displayName": display_name,
                "password": password,
                "customizationColor": "primary",
                "wakuV2LightClient": False,
                "thirdpartyServicesEnabled": True,
            }
        else:
            self.logger.info(f"Logging in with Key UID - {key_uid}")

        if is_new_account:
            self.logger.info(f"Creating account with display_name {display_name}")
            url_key = "create"

        if is_recovery:
            url_key = "restore"
            params["mnemonic"] = mnemonic
            self.logger.info(f"Restoring account for given mnemonics")

        self.logout()
        url = self.urls["http"][url_key]
        response = requests.post(url, json=params)
        signal_event = self.__signal.get("node.login")
        if signal_event["is_error"]:
            raise Exception(f"There was an error with Status Backend...\n{signal_event['error_message']}")

        self.logger.info("Successfully logged in!")
        event: dict = signal_event["event"]["settings"]
        self.__info = {
            "public_key": event["public-key"],
            "url": None,
            "emojis": event["emojiHash"],
            "key_uid": event["key-uid"],
            "compressed_key": event["compressedKey"],
            "mnemonic": event.get("mnemonic", mnemonic),
            "display_name": event["display-name"],
            "bio": event.get("bio", ""),
            "password": password,
            "wallet_address": event["dapps-address"],
            "logged_in_timestamp": datetime.datetime.now()
        }
        self.__info["url"] = self.__call_rpc("urls", "shareUserURLWithData", [event["public-key"]]).get("result")
        # Messenger can be activated only when logged in
        self.__start_messenger()
        if is_recovery:
            self.logger.info("Updating remote display name")
            self.display_name = event["display-name"]
            self.logger.info("Successfully updated display name!")
            self.__load_backup()

        return self

    def logout(self):
        """
        Logout of Status app. In a way this method behaves as a Status cleaner
        """
        response = requests.post(self.urls["http"]["logout"])
        self.__info = {}
        self.__is_messenger_launched = False
        return self

    @property
    def logger(self) -> logging.Logger:
        return self.__logger

    @property
    def available_accounts(self) -> list[dict]:
        """
        All locally available accounts
        """
        response = requests.post(self.urls["http"]["initialize"], json={
            "dataDir": self.__docker_data_folder
        })
        data: dict = response.json()
        accounts: list[dict] = data.get("accounts", [])
        if not isinstance(accounts, list):
            accounts = []

        current_available_accounts = [
            {
                "display_name": account["name"],
                "key_uid": account["key-uid"],
                "created_at": datetime.datetime.fromtimestamp(account["timestamp"])
            }
            for account in accounts
        ]
        return current_available_accounts

    @property
    def info(self) -> dict:
        """
        Overall information for currently logged in account.
        Can also be used to verify if the user has logged in.
        """
        if not self.__info:
            raise Exception("Make sure you are logged in to your Status account with login() first...")
        return self.__info

    @property
    def display_name(self) -> str:
        """
        Get the current display name
        """
        return self.info["display_name"]

    @display_name.setter
    def display_name(self, name: str):
        self.__validate_display_name(name)
        output = self.__call_rpc("messaging", "setDisplayName", [name])
        # It seems that if a valid name is given, it will be instantly updated
        # However after tracing the signals, an `envelope.sent` is sent a bit
        # after the name has been changed.
        self.signal.get("envelope.sent")
        self.__info["display_name"] = name

    @property
    def bio(self) -> str:
        """
        Get the current bio
        """
        return self.info["bio"]

    @bio.setter
    def bio(self, bio: Any):
        if isinstance(bio, type(None)):
            bio = ""

        bio = str(bio).strip()
        # Limit based from Status App
        CHARACTERS = 240
        if len(bio) > CHARACTERS:
            raise ValueError(f"Bio cannot be longer than {CHARACTERS} characters...")

        self.__call_rpc("messaging", "setBio", [bio])
        # It seems that if a valid bio is given, it will be instantly updated
        # However after tracing the signals, an `envelope.sent` is sent a bit
        # after the bio has been updated.
        self.signal.get("envelope.sent")
        self.__info["bio"] = bio

    @bio.deleter
    def bio(self):
        self.bio = ""

    @property
    def contacts(self) -> dict[str, dict]:
        """
        Get the contacts that the bot has.
        This includes contacts that have interacted with us. If a contact has removed us (or the bot has removed us)

        NOTE: We do not use internal state so we can get dynamic values such as:
        - Is currently active
        - Is currently blocked
        - Current display name
        - Current bio

        Terminology for Status contact requests:
            - approved - when both `contact_state` and `external_contact_state` are `mutual`
            - sent request - when `contact_state` is `sent` and `external_contact_state` is `none`
            - received request - when `contact_state` is `received`
        """
        data = self.__call_rpc("messaging", "contacts")
        raw: list[dict] = data.get("result", [])
        if not raw:
            return {}

        # dict format can be used in restricting functionality
        # such as - `send_message` and `remove_contact`
        contacts = {
            contact["id"]: {
                "public_key": contact["id"],
                "url": self.__call_rpc("urls", "shareUserURLWithData", [contact["id"]]).get("result"),
                "chat_id": contact["id"],
                "key_uid": contact["compressedKey"],
                "emojis": contact["emojiHash"],
                "contact_state": self.__mappings["contact_request"][contact["contactRequestState"]],
                "external_contact_state": self.__mappings["contact_request"][contact["contactRequestRemoteState"]],
                "has_added_us": contact["hasAddedUs"],
                "added": contact["added"],
                "mutual": contact["mutual"],
                "display_name": contact["displayName"],
                "bio": contact["bio"],
                "wallet_address": contact["address"],
                "last_updated": datetime.datetime.fromtimestamp(contact["lastUpdated"] / self.__timestamp_divisor) if contact["lastUpdated"] > 0 else None
            }
            for contact in raw
        }
        return contacts

    @property
    def signal(self) -> Signal:
        """
        Work with different Status event signals.
        To get a full list of all available signals,
        feel free to use `signal.available_signals`.
        """
        self.info
        return self.__signal

    @property
    def communities(self) -> list[dict]:
        """
        Get the communities that the bot is in.
        NOTE: We do not use internal state so we can get dynamic values such as:
        - Current community description
        - Current number of community members
        - Current channels' names, descriptions and permissions
        """
        data = self.__call_rpc("messaging", "communities")
        raw: list[dict] = data.get("result", [])
        if not raw:
            return []

        to_datetime = lambda key, mapping: (datetime.datetime.fromtimestamp(mapping[key]) if mapping[key] > 0 else None) if key in mapping else None
        communities = [
            {
                "id": community["id"],
                "url": self.__call_rpc("urls", "shareCommunityURLWithData", [community["id"]]).get("result"),
                "name": community["name"],
                "verified": community["verified"],
                "description": community["description"],
                "dialog": community["introMessage"],
                "leaving_message": community["outroMessage"],
                "tags": community["tags"],
                "is_member": community["isMember"],
                "joined": community["verified"],
                "joined_timestamp": to_datetime("joinedAt", community),
                "requested_timestamp": to_datetime("requestedToJoinAt", community),
                "encrypted": community["encrypted"],
                "members": len(community["members"]),
                "channels": [
                    {
                        "id": chat["id"],
                        "chat_id": community["id"] + chat["id"],
                        "url": self.__call_rpc("urls", "shareCommunityChannelURLWithData", [community["id"], chat["id"]]).get("result"),
                        "name": chat["name"],
                        "description": chat["description"],
                        "permissions": {
                            "posting": chat["canPost"],
                            "viewing": chat["canView"],
                            "reactions": chat["canPostReactions"],
                            "token_gated": chat["tokenGated"]
                        }
                    }
                    for chat in community["chats"].values()
                ]
            }
            for community in raw
        ]
        return communities

    @property
    def chats(self) -> list[dict]:
        """
        All chats that the bot can send messages to.
        This property combines `self.communities` and `self.contacts` chats.
        """
        communities = [
            {"type": "channel", "id": chat["chat_id"], "name": f"{community['name']} #{chat['name']}"}
            for community in self.communities
            for chat in community["channels"]
            if chat["permissions"]["posting"]
        ]
        contacts = [
            {"type": "contact", "id": contact["chat_id"], "name": contact["display_name"]}
            for contact in self.contacts.values()
        ]

        # Group chats in RPC endpoint are chat type 3
        data = self.__call_rpc("messaging", "activeChats")
        result: Optional[list[dict]] = data.get("result", [])
        if not result:
            result = []

        group_chats = [
            {"type": "group_chat", "id": active_chat["id"], "name": active_chat["name"]}
            for active_chat in result
            if active_chat["chatType"] == 3
        ]
        return contacts + communities + group_chats

    def send_message(self, chat_id: str, message: str):
        """
        Send a message to the given chat.

        Parameters:
            - `chat_id` - the chat ID can be found in `self.chats`
            - `message` - the message that will be sent. Currently only text messages are supported
        """
        params = [{
            "chatId": chat_id,
            "text": message,
            "contentType": 1, # Send message only. Future versions can have different message types (audio, image, etc.)
            "responseTo": ""
        }]
        self.__call_rpc("messaging", "sendChatMessage", params)

    def listen_messages(self) -> Generator:
        """
        Listen for new **RAW** messages continuously. Can be used for real time processing.
        """
        for message in self.signal.listen("messages.new"):
            event: dict = message.get("event", {})
            if "chats" in event or "messages" in event:
                yield message

    def get_messages(self, chat_id: str, start_timestamp: Optional[datetime.datetime] = None, end_timestamp: Optional[datetime.datetime] = None) -> list[dict]:
        """
        Get all of the messages in the given start and end timestamps.
        Messages are returned in descending order (newest to oldest).
        Messages can be fetched for removed contacts as well.

        Parameters:
            - `chat_id` - the chat ID can be found in `self.chats`
            - `start_timestamp` - the start timestamp for message extraction. If not provided all early messages will be fetched.
            - `end_timestamp` - the end timestamp for message extraction. If not provided all latest messages will be fetched.
        """
        # NOTE: Order of params matters when making the RCP call
        params = {
            "chat_id": chat_id,
            "cursor": "",
            "limit": 500
        }
        all_messages = []
        # Keys that need to be converted to datetime.datetime
        timestamp_keys = []

        finished = False
        while not finished:
            data = self.__call_rpc("messaging", "chatMessages", list(params.values()))
            result: dict[str, Union[str, list[dict]]] = data.get("result", {})
            messages: Optional[list[dict]] = result.get("messages")
            cursor: Optional[str] = result.get("cursor")
            if not cursor:
                cursor = ""
            if not messages:
                messages = []

            if messages and not timestamp_keys:
                timestamp_keys = [key for key in result["messages"][0].keys() if "timestamp" in key.lower()]

            for message in messages:
                point = {
                    self.__camel_to_snake(key): value if key not in timestamp_keys else datetime.datetime.fromtimestamp(value / self.__timestamp_divisor)
                    for key, value in message.items()
                }

                if start_timestamp and point["timestamp"] < start_timestamp:
                    finished = True
                    break

                if end_timestamp and point["timestamp"] > end_timestamp:
                    continue

                all_messages.append(point)

            if len(cursor) > 0:
                params["cursor"] = cursor
            else:
                finished = True

        return all_messages

    def add_contact(self, public_key: str, display_name: Optional[str] = None):
        """
        Send a contact request / approve a contact.

        Parameters:
            - `public_key` - the contact's public key
            - `display_name` - this field is required if the `public_key` does not appear in your contacts. This will set their display name (can be different from the one the other user has chosen)
        """
        contacts = list(self.contacts.values())
        if not display_name:
            for contact in contacts:
                if public_key != contact["public_key"]:
                    continue

                display_name = contact["display_name"]
                break

        if not display_name:
            raise ValueError(f"Cannot add contact {public_key}...\nPlease make sure you add display_name for contacts that you are sending friend requests to and have never interacted with before!")

        params = [{"id": public_key, "nickname": "", "displayName": display_name, "ensName": ""}]
        self.__call_rpc("messaging", "addContact", params)
        return self

    def remove_contact(self, public_key: str) -> bool:
        """
        Remove the contact / decline a contact request.

        Parameters:
            - `public_key` - the contact's public key

        Output:
            - If `True` the user has been removed. If `False` the user has not been removed (either not a contact or not a friend)
        """
        contact_info = self.contacts.get(public_key, {})
        # Cannot remove a contact that is not in your contact
        if not contact_info:
            return False
        # Contact has already been removed
        if contact_info["contact_state"] == "none":
            return False
        params = [public_key]
        self.__call_rpc("messaging", "removeContact", params)
        return True

    def send_request_community(self, url: str) -> Optional[datetime.datetime]:
        """
        Send a request to join a community

        Parameters:
            - `url` - the community's URL

        Output:
            - the timestamp the request was sent
        """
        data = self.__call_rpc("urls", "parseSharedURL", [url])
        raw: dict = data.get("result", {})
        community_key = raw["community"]["communityId"]

        params = [{"communityKey": community_key, "waitForResponse": True, "tryDatabase": True}]
        data = self.__call_rpc("messaging", "fetchCommunity", params)
        raw: dict = data.get("result", {})
        community_id = raw["id"]

        params = [{
            "communityId": community_id,
            "addressesToReveal": [self.info["wallet_address"]],
            "airdropAddress": self.info["wallet_address"]
        }]
        data = self.__call_rpc("messaging", "requestToJoinCommunity", params)
        return datetime.datetime.fromtimestamp(raw.get("requestedToJoinAt", datetime.datetime.now().timestamp()))

    def backup(self) -> str:
        """
        Create a `.bkp` (Backup) for the account. If the backup was not successful, a custom exception will be raised.

        Output:
            - the Docker backup path (linked to a volume). The file name is unique per account.
        """
        self.info
        response = requests.post(self.urls["http"]["create_backup"])
        result: dict = response.json()
        file_path = result.get("filePath")

        if not file_path or (isinstance(file_path, str) and len(file_path) == 0):
            raise Exception(f"There was an error with creating a backup for {self.info['display_name']}")

        return file_path

    def __start_messenger(self):
        """
        Start the decentralized messaging service.
        This is required for messages to be received / sent.
        """
        if self.__is_messenger_launched:
            return
        self.logger.info("Starting messaging")
        self.__call_rpc("messaging", "startMessenger")
        self.__signal.get("wakuv2.peerstats")
        self.__is_messenger_launched = True
        self.logger.info("Messaging launched")

    def __del__(self):
        """
        Handles automatic logout when calling `del`
        and after running `python`
        """
        try:
            self.logout()
        except Exception:
            pass

        try:
            self.__signal.close(None)
        except Exception:
            pass

    def call_rpc(self, prefix: str, method_name: str, params: Optional[Union[list, dict]] = None) -> dict:
        """
        For faster development purposes
        """
        return self.__call_rpc(prefix, method_name, params)

    def __load_backup(self):
        """
        Try to load every file in the Docker volume
        when an account recover is done.
        """
        for file_name in os.listdir(self.__backup_local_folder):
            params = {
                "filePath": os.path.join(self.__docker_backup_folder, file_name)
            }
            self.logger.info(f"Trying to load {file_name}")
            response = requests.post(self.urls["http"]["load_backup"], json=params)
            error: str = response.json().get("error", "")
            if len(error) == 0:
                self.__signal.get("messages.new")
                self.logger.info(f"Successfully loaded file!")
                break

            self.logger.warning(error)

    def __call_rpc(self, prefix: str, method_name: str, params: Optional[Union[list, dict]] = None) -> dict:
        """
        Make RPC calls to Status Backend

        Parameters:
            - `prefix` - the prefix of the method name
            - `method_name` - the method name as it is in the backend
            - `params` - RPC call parameters

        Output:
            - the raw output from the RPC method
        """
        # Quick initialization check - RPC calls
        # can be made only after the user has logged in
        self.info
        name = self.__prefix_mapping.get(prefix)
        if not name:
            raise ValueError(f"Name {name} does not exist... Available options: {list(self.__prefix_mapping.keys())}")

        data = {
            'jsonrpc': '2.0',
            # NOTE: Waku may be renamed to Logos Messaging (or something similar)
            'method': f'{name}_{method_name}',
            'id': None # Original code has an incrementing ID but it does not make a difference
        }
        if params:
            data["params"] = params

        response = requests.get(self.urls["http"]["rpc"], json=data)
        return response.json()

    def __camel_to_snake(self, name: str) -> str:
        """
        Used to make camel case Status Backend keys
        more Pythonic (snake case). Function is used
        when the entire raw data point is returned.

        Parameters:
            - `name` - camel case dictionary key

        Output:
            - snake case `name`
        """
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
        s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
        return s2.lower()

    def __validate_display_name(self, name: str) -> bool:
        """
        Validate the display name based on Status App rules.
        Validation most probably is dealt with on the GUI side
        of the application instead of the backend.

        Status App validation rules:
            - Use A-Z and 0-9, hyphens and underscores only
            - Display name must be at least 5 characters long
            - Display name can't start or end with a space

        Parameters:
            - `name` - the name that the user wants to use to login / create account / change

        Output:
            - `True` if the name was successfully changed. A
        """
        if name != name.strip():
            raise ValueError("Display name cannot start or end with a space.")

        if len(name) < 5:
            raise ValueError("Display name must be at least 5 characters long.")

        if len(name) > 24:
            raise ValueError("Display name cannot be more than 24 characters long.")

        if not re.fullmatch(r"[A-Za-z0-9 _-]+", name):
            raise ValueError("Display name can contain only A-Z, 0-9, hyphens (-), underscores (_) and spaces.")

        return True
