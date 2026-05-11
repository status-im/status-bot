import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .models import Base

logger = logging.getLogger(__name__)


class Database:

    def __init__(self, db_type: str, host: str, port: int, user: str, password: str, name: str, schema: str):
        self._type = db_type
        self._schema = schema
        self._url = self._build_url(db_type, host, port, user, password, name)
        self._engine = create_engine(self._url)
        self._session_factory = sessionmaker(bind=self._engine)

    def create_tables(self, tables=None):
        Base.metadata.create_all(self._engine, tables=tables)
        logger.info("Database tables initialized")

    def _build_url(self, db_type: str, host: str, port: int, user: str, password: str, name: str) -> str:
        if db_type == "postgres":
            return f"postgresql://{user}:{password}@{host}:{port}/{name}"
        elif db_type == "sqlite":
            return f"sqlite:///{name}"
        raise ValueError(f"Unsupported database type: {db_type}")

    def session(self):
        return self._session_factory()

    def execute(self, query: str):
        with self._engine.begin() as conn:
            conn.execute(text(query))

    def close(self):
        self._engine.dispose()