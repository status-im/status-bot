from sqlalchemy import Column, String, DateTime

from .base import Base


class FeedbackMessage(Base):
    __tablename__ = "feedback_message"
    id = Column(String, primary_key=True)
    public_key = Column(String, nullable=False)
    request_timestamp = Column(DateTime, nullable=False)
    group_chat_message_id = Column(String, nullable=True)
    response_timestamp = Column(DateTime, nullable=True)
    response_message = Column(String, nullable=True)
    reply_chat_id = Column(String, nullable=True)
    reply_group_id = Column(String, nullable=True)
