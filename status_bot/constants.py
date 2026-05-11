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
