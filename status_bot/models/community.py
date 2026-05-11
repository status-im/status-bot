from sqlalchemy import Boolean, Column, DateTime, Integer, String

from .base import Base

class Community(Base):
    __tablename__ = "community"
    id = Column(String, primary_key=True)
    url = Column(String, nullable=True)
    name = Column(String, nullable=True)
    verified = Column(Boolean, nullable=True)
    tags = Column(String, nullable=True)
    is_member = Column(Boolean, nullable=True)
    joined = Column(Boolean, nullable=True)
    joined_timestamp = Column(DateTime, nullable=True)
    requested_timestamp = Column(DateTime, nullable=True)
    encrypted = Column(String, nullable=True)
    number_members = Column(Integer, nullable=True)
