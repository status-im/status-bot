from sqlalchemy import Column, DateTime, Float, String, Boolean

from .base import Base

class ContactRequest(Base):
    __tablename__ = "contact_request"

    id = Column(String, primary_key=True)
    public_key = Column(String, nullable=False)
    request_message = Column(String, nullable=True)
    request_timestamp = Column(DateTime, nullable=False)
    conversation_id = Column(String, nullable=True)
    last_engagement_message = Column(Float, default=0)
    is_new_user = Column(Boolean, default=True)
