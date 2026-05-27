import logging

import pandas as pd
from typing import Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError, NoSuchTableError

from .models import Base


class Database:

    def __init__(self, db_type: str, host: str, port: int, user: str, password: str, name: str, schema: str):
        self._type = db_type
        self._schema = schema
        self._url = self._build_url(db_type, host, port, user, password, name)
        self._engine = create_engine(self._url)
        self._logger = logging.getLogger("status_bot.database")

    def init_tables(self):
        Base.metadata.create_all(self._engine)
        self._logger.info("Database tables initialized")

    def _build_url(self, db_type: str, host: str, port: int, user: str, password: str, name: str) -> str:
        if db_type == "postgres":
            return f"postgresql://{user}:{password}@{host}:{port}/{name}"
        elif db_type == "sqlite":
            return f"sqlite:///{name}"
        raise ValueError(f"Unsupported database type: {db_type}")

    def insert(self, data: pd.DataFrame, table_name: str, json_columns: Optional[list] = None):
        if len(data) == 0:
            return

        if self._type == "postgres":
            with self._engine.begin() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self._schema}"))

        data.columns = [column.lower() for column in data.columns]

        params = {
            "name": table_name,
            "con": self._engine,
            "schema": self._schema,
            "if_exists": "append",
            "index": False,
        }
        if json_columns and self._type == "postgres":
            params["dtype"] = {col: JSONB for col in json_columns}

        existing_columns = self.get_columns(table_name)
        if existing_columns:
            for column in data.columns:
                if column not in existing_columns:
                    with self._engine.begin() as conn:
                        conn.execute(
                            text(f"ALTER TABLE {self._schema}.{table_name} ADD COLUMN {column} TEXT")
                        )

        try:
            data.to_sql(**params)
        except IntegrityError:
            self._logger.warning(f"Duplicate rows skipped in {table_name}")

    def execute(self, query: str):
        with self._engine.begin() as conn:
            conn.execute(text(query))

    def to_pandas(self, query: str) -> pd.DataFrame:
        return pd.read_sql(query, self._engine)

    def get_columns(self, table_name: str) -> list[str]:
        insp = inspect(self._engine)
        try:
            columns = insp.get_columns(table_name, schema=self._schema)
        except NoSuchTableError:
            return []
        return [col["name"] for col in columns]

    def close(self):
        self._engine.dispose()
