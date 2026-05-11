from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String

from .base import Base


class Channel(Base):
    __tablename__ = "channel"
    id = Column(String, primary_key=True)
    chat_id = Column(String, primary_key=True)
    community_id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    description = Column(String, nullable=True)
    can_post = Column(Boolean, nullable=True)
    can_view = Column(Boolean, nullable=True)
    can_post_reaction = Column(Boolean, nullable=True)
    token_gated = Column(String, nullable=True)


