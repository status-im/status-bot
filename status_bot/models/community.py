from sqlalchemy import JSON, REAL, BigInteger, Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class RawCommunityInfo(Base):
    __tablename__ = "raw_community_info"

    id = Column(String, primary_key=True)
    url = Column(String, nullable=True)
    name = Column(String, nullable=True)
    verified = Column(Boolean, nullable=True)
    tags = Column(JSONType, nullable=True)
    is_member = Column(Boolean, nullable=True)
    joined_timestamp = Column(DateTime, nullable=True)
    requested_timestamp = Column(DateTime, nullable=True)
    encrypted = Column(Boolean, nullable=True)
    members = Column(BigInteger, nullable=True)
    channels = Column(JSONType, nullable=True)
    batch_timestamp = Column(DateTime, primary_key=True)


class RawMessage(Base):
    __tablename__ = "raw_messages"

    id = Column(String, primary_key=True)
    whisper_timestamp = Column(DateTime, nullable=True)
    from_ = Column("from", String, nullable=True)
    seen = Column(Boolean, nullable=True)
    chat_id = Column(String, nullable=True)
    community_id = Column(String, nullable=True)
    message_type = Column(BigInteger, nullable=True)
    response_to = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=True)
    deleted = Column(Boolean, nullable=True)
    extracted_timestamp = Column(DateTime, nullable=True)
    toxicity = Column(REAL, nullable=True)
    severe_toxicity = Column(REAL, nullable=True)
    obscene = Column(REAL, nullable=True)
    threat = Column(REAL, nullable=True)
    insult = Column(REAL, nullable=True)
    identity_attack = Column(REAL, nullable=True)
    source = Column(String, nullable=True)
    batch_timestamp = Column(DateTime, nullable=True)
