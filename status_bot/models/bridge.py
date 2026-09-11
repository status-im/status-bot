from sqlalchemy import BigInteger, Boolean, Column, DateTime, String
from .base import Base


class BridgeInfo(Base):
    __tablename__ = "bridge_info"

    id = Column(String)
    topic_id = Column(BigInteger, nullable=True)
    post_id = Column(BigInteger, nullable=True)
    post_number = Column(BigInteger, nullable=True)
    reply_to = Column(String, nullable=True)
    user_id = Column(BigInteger, nullable=True)
    username = Column(String, nullable=True)
    markdown_text = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    post_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    slug = Column(String, nullable=True)
    message_id = Column(String, primary_key=True)
    chat_id = Column(String, nullable=True)
    source = Column(String, nullable=True)
    is_open = Column(Boolean, nullable=True)
