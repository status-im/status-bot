from pandas.core.arrays import boolean
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String

from .base import Base


class ReceivedChat(Base):
    __tablename__ = "received_chats"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=True)
    name = Column(String, nullable=True)
    received_timestamp = Column(DateTime, nullable=True)
    salt = Column(String, nullable=True)
    description = Column(String, nullable=True)
    color = Column(String, nullable=True)
    emoji = Column(String, nullable=True)
    active = Column(Boolean, nullable=True)
    viewers_can_post_reactions = Column(Boolean, nullable=True)
    chat_type = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=True)
    last_clock_value = Column(BigInteger, nullable=True)
    deleted_at_clock_value = Column(Integer, nullable=True)
    read_messages_at_clock_value = Column(Integer, nullable=True)
    unviewed_messages_count = Column(Integer, nullable=True)
    unviewed_mentions_count = Column(Integer, nullable=True)
    membership_update_events = Column(Integer, nullable=True)
    identicon = Column(String, nullable=True)
    muted = Column(String, nullable=True)
    mute_till = Column(boolean, nullable=True)
    community_id = Column(String, nullable=True)
    category_id = Column(String, nullable=True)
    joined = Column(String, nullable=True)
