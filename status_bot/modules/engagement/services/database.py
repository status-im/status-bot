import logging
from typing import Optional, Any
from prometheus_client import Counter
from sqlalchemy import and_
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from status_bot.models import FeedbackMessage, EngagementContactRequest
from status_sdk.models import Message

logger = logging.getLogger(__name__)


def get_all_contact_to_contact(db_session: Session, delay: int, delay_unit: str):
    threshold = datetime.now() - timedelta(days=delay)
    if delay_unit != "days":
        threshold = datetime.utcnow() - timedelta(minutes=delay)
    logger.debug(f"Threshold {threshold}")

    return (
        db_session.query(EngagementContactRequest)
        .filter(
            and_(
                EngagementContactRequest.request_timestamp < threshold,
                EngagementContactRequest.last_engagement_message < delay,
                EngagementContactRequest.is_new_user,
            )
        )
        .all()
    )


def get_response_reply_if_exist(db_session: Session, message: Message) -> Optional[str]:
    if not message.reply_id:
        return None

    logger.info(f"replying to message {message.reply_id}")
    reply_to = (
        db_session.query(FeedbackMessage)
        .filter(FeedbackMessage.reply_chat_id == message.reply_id)
        .first()
    )
    logger.info(f"Original Message here {reply_to}")
    if reply_to:
        return reply_to.reply_chat_id

    return None


def find_original_message_if_exists(
    message: Message, db_session: Session, _counter: Counter
) -> Optional[EngagementContactRequest]:
    """
    Fetch in database the original Message matching the reply_id
    Parameters:
        - message: received message
        - session: ORM database session
        - _counter: Prometheus Metrics Counter
    """
    if message.reply_id is None:
        logger.debug("The message isn't a reply, ignoring it")
        return None
    original_message: FeedbackMessage = (
        db_session.query(FeedbackMessage)
        .filter(FeedbackMessage.group_chat_message_id == message.reply_id)
        .first()
    )
    if original_message is None:
        logger.warning(f"No original message found for id {message.reply_id}")
        _counter.labels(type="original-not-found").inc()
        return None
    return original_message


def remove_contact(message: EngagementContactRequest, db_session: Session, _counter: Counter):
    """
    Function to handle removal of contact.
    When a user remove the bot as a contact, all data with the user public key
    Parameters:
        - message: first message part of the event content transmitted by the Backend
        - session: ORM database session
        - _counter: Prometheus Metrics Counter

    """
    user_public_key = message.public_key
    logger.info("Received a Contact Removal")
    db_session.query(FeedbackMessage).filter(FeedbackMessage.public_key == user_public_key).delete()
    db_session.query(EngagementContactRequest).filter(
        EngagementContactRequest.public_key == user_public_key
    ).delete()
    db_session.commit()
    _counter.labels(type="contact-removed").inc()


def delete_old_messages(db_session: Session, settings: dict[str, Any], _counter: Counter):
    """
    Delete all feedback messages stored for longer than the configured
    `retention_time` (default: 90 days).
    In order to not store not necessary data.
    Parameters:
        - db_session: ORM database session
        - settings: dict of settings
        - _counter: Prometheus Metrics Counter
    """
    retention_time = settings.get("retention_time", 90)
    threshold = datetime.now() - timedelta(days=retention_time)
    # For testing purpose
    if settings.get("delay_type", "days") != "days":
        threshold = datetime.utcnow() - timedelta(minutes=retention_time)
    logger.debug(f"Threshold {threshold} for message deletion")
    msgs = (
        db_session.query(FeedbackMessage)
        .filter(FeedbackMessage.request_timestamp < threshold)
        .all()
    )
    logger.info(
        f"Deleting {len(msgs)} messages having reach the retention time of {retention_time}"
    )
    for msg in msgs:
        db_session.delete(msg)
        _counter.labels(type="periodic-message-del").inc()
    db_session.commit()
