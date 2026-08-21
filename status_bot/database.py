import logging

from typing import Any, Optional

from sqlalchemy import create_engine, text, Row, inspect
from sqlalchemy.exc import IntegrityError, NoSuchTableError
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSONB
from .models import Base

import pandas as pd

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

    def _build_url(self, db_type: str, host: str, port: int, user: str, password: str, name: str) -> str:
        if db_type == "postgres":
            return f"postgresql://{user}:{password}@{host}:{port}/{name}"
        elif db_type == "sqlite":
            return f"sqlite:///{name}"
        raise ValueError(f"Unsupported database type: {db_type}")

    @property
    def engine(self) -> Engine:
        return self._engine

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

    def execute(self, query: str):
        with self._engine.begin() as conn:
            conn.execute(text(query))

    def fetch_all(self, query: str, params: Optional[dict[str, Any]] = None) -> list[Row]:
        with self._engine.connect() as conn:
            return conn.execute(text(query), params or {}).fetchall()

    def close(self):
        self._engine.dispose()

    def insert(self, data: pd.DataFrame, table_name: str, schema_name: str, json_columns: Optional[list] = None):
        if len(data) == 0:
            return

        if self._type == "postgres":
            with self._engine.begin() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))

        data.columns = [column.lower() for column in data.columns]

        params = {
            "name": table_name,
            "con": self._engine,
            "schema": schema_name,
            "if_exists": "append",
            "index": False,
        }
        if json_columns and self._type == "postgres":
            params["dtype"] = {col: JSONB for col in json_columns}

        existing_columns = self.get_columns(table_name, schema_name)
        if existing_columns:
            for column in data.columns:
                if column not in existing_columns:
                    with self._engine.begin() as conn:
                        conn.execute(
                            text(f"ALTER TABLE {schema_name}.{table_name} ADD COLUMN {column} TEXT")
                        )

        try:
            data.to_sql(**params)
        except IntegrityError:
            logger.warning(f"Duplicate rows skipped in {table_name}")

    def get_columns(self, table_name: str, schema_name: str) -> list[str]:
        insp = inspect(self._engine)
        try:
            columns = insp.get_columns(table_name, schema=schema_name)
        except NoSuchTableError:
            return []
        return [col["name"] for col in columns]
