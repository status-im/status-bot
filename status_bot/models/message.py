from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String

from .base import Base


class ReceivedMessage(Base):
    __tablename__ = "received_messages"

    id = Column(String, primary_key=True)
    whisper_timestamp = Column(DateTime, nullable=True)
    from_ = Column("from", String, nullable=True)
    alias = Column(String, nullable=True)
    seen = Column(Boolean, nullable=True)
    rtl = Column(Boolean, nullable=True)
    line_count = Column(Integer, nullable=True)
    text = Column(String, nullable=True)
    chat_id = Column(String, nullable=True)
    local_chat_id = Column(String, nullable=True)
    clock = Column(BigInteger, nullable=True)
    replace = Column(String, nullable=True)
    response_to = Column(String, nullable=True)
    ens_name = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=True)
    content_type = Column(Integer, nullable=True)
    message_type = Column(Integer, nullable=True)
    contact_request_state = Column(Integer, nullable=True)
    compressed_key = Column(String, nullable=True)
    received_timestamp = Column(DateTime, nullable=True)
