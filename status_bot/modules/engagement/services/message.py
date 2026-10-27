import logging
from typing import Optional, Any
from prometheus_client import Counter
from status_bot.modules.engagement.constant import IGNORED_MSG_CONTENT_TYPE, REPLY_MSG_ERROR_IMG
from status_bot.modules.utils import download_image

from status_sdk.models import Message
from status_sdk.account import Account


logger = logging.getLogger(__name__)


def should_process_messages(message: Message, bot_compressed_key: str) -> bool:
    """
    This function determind if the message is of the correct type and not from the bot itself.

    Parameters:
        - message: Message to process

    Output:
        - Flag to process or not
    """
    # TODO remove later
    if message.from_public_key == bot_compressed_key:
        return False
    if message.content_type in IGNORED_MSG_CONTENT_TYPE:
        return False
    return True


def is_feedback_message(message: Message, settings: dict[str, Any]) -> bool:
    """
    Verify if the message concerne the feedback or is concidered spam.
    Use only the first message since multiple messages are image album
    and sahre the same text.
    """
    feedback_keywords = settings.get("feedback_keywords", [])
    return any(kw in message.content.lower() for kw in feedback_keywords)


def send_message(
    chat_id: str,
    original_message: Message,
    reply_id: Optional[str],
    account: Account,
    settings: dict[str, Any],
    _counter: Counter,
):
    """
    Send message to either the group chat or the user.
    Download an image with there is an image to transfer.
    Parameters:
        - chat_id: Id of the chat to contact
        - original_message: Message to transfer
        - msg_content: content of the message to tranfert
        - reply_id: optional id of the message that require a reply
    Ouput:
        - message id
    """
    logger.info(
        f"Original received : {original_message.content_type} - {original_message.image_urls}"
    )
    send_msg_id = None
    if len(original_message.image_urls) == 0:
        send_msg_id = account.send_message(
            chat_id=chat_id, message=original_message.text, reply_to_message_id=reply_id
        )
        return send_msg_id
    message_to_send = original_message.text
    images_path = []
    for path in original_message.image_urls:
        image_id = path.split("messageId=", 1)[1]
        image_path = f"{settings.get('image_folder')}/{image_id}"
        logger.info(f"Path Inaital {path} - path to send {image_path}")
        try:
            logger.debug(f"Downloading image at the path {image_path}")
            download_image(
                url=path.replace("localhost", "backend"),
                image_path=image_path,
            )
            logger.info(f"Download image {image_path}")
            images_path.append(image_path)
        except Exception as e:
            logger.error(e)
            _counter.labels(type="error-image-download").inc()
            message_to_send = f"{message_to_send} {REPLY_MSG_ERROR_IMG}"
    send_msg_id = account.send_image(
        chat_id=chat_id,
        file_paths=images_path,
        message=message_to_send,
        reply_to_message_id=reply_id,
    )
    logger.info("after send")
    return send_msg_id
