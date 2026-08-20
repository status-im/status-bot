from enum import Enum

_MESSAGE_DETERMINISTIC_COLUMNS = [
    "id",
    "from",
    "response_to",
    "chat_id",
    "local_chat_id",
    "display_name",
    "ens_name",
    "alias",
    "text",
]

_MESSAGE_DROP_COLUMNS = [
    "parsed_text",
    "quoted_message",
    "emoji_hash",
    "gap_parameters",
]

_CHAT_DETERMINISTIC_COLUMNS = [
    "id",
    "name",
]

class EventTypeEnum(Enum):
    MESSAGE = "messages.new"
    LOCAL_NOTIFICATION = "local-notifications"

class NotificationCategoryEnum(Enum):
    CONTACT_REQUEST = "contactRequest"
    NEW_MESSAGE = "newMessage"
    GROUP_INVITE = "groupInvite"
    COMMUNITY_REQUEST_TO_JOIN = "communityRequestToJoin"
    COMMUNITY_JOINED = "communityJoined"
