import logging

from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_type: str, host: str, port: int, user: str, password: str, name: str):
        self._type = db_type
        self._url = self._build_url(db_type, host, port, user, password, name)
        self._engine = create_engine(self._url)
        self._binds: dict[str, Engine] = {}
        self._session_factory = sessionmaker(bind=self._engine)

    def create_tables(self, schema_name: Optional[str] = None, tables=None):
        if schema_name and self._type == "postgres":
            with self._engine.begin() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))

        Base.metadata.create_all(self.__bind(schema_name), tables=tables)
        logger.info(f"Database tables initialized in schema {schema_name or 'default'}")

    def _build_url(
        self, db_type: str, host: str, port: int, user: str, password: str, name: str
    ) -> str:
        if db_type == "postgres":
            return f"postgresql://{user}:{password}@{host}:{port}/{name}"
        elif db_type == "sqlite":
            return f"sqlite:///{name}"
        raise ValueError(f"Unsupported database type: {db_type}")

    def session(self, schema_name: Optional[str] = None) -> Session:
        return self._session_factory(bind=self.__bind(schema_name))

    def __bind(self, schema_name: Optional[str]) -> Engine:
        # sqlite has no schemas, so unqualified names are the only option there
        if not schema_name or self._type != "postgres":
            return self._engine

        if schema_name not in self._binds:
            self._binds[schema_name] = self._engine.execution_options(
                schema_translate_map={None: schema_name}
            )
        return self._binds[schema_name]
