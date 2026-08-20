from sqlalchemy import  Column, DateTime, BigInteger, String

from .base import Base

class ContactRequest(Base):
    __tablename__ = "contact_request"

    id = Column(String, primary_key=True)
    public_key = Column(String, nullable=False)
    contact_name = Column(String, nullable=False)
    request_message = Column(String, nullable=True)
    request_timestamp = Column(BigInteger, nullable=False)
    conversation_id = Column(String, nullable=True)
