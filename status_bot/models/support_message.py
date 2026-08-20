from sqlalchemy import  Column, BigInteger, String

from .base import Base

class SupportMessage(Base):
    __tablename__ = "support_message"
    id = Column(String, primary_key=True)
    public_key = Column(String, nullable=False)
    request_message = Column(String, nullable=True)
    request_timestamp = Column(BigInteger, nullable=True)
    chat_id = Column(String, nullable=True)
    group_support_message_id = Column(String, nullable=True)
    response_timestamp = Column(BigInteger, nullable=True)
    response_message = Column(String, nullable=True)
