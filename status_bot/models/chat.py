from sqlalchemy import Column, DateTime, String

from .base import Base


class ReceivedChat(Base):
    __tablename__ = "received_chats"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=True)
    name = Column(String, nullable=True)
    received_timestamp = Column(DateTime, nullable=True)
    salt = Column(String, nullable=True)
