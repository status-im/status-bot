import datetime
import logging

import pandas as pd
from typing import Optional
from sqlalchemy import DateTime, create_engine, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError, NoSuchTableError
from sqlalchemy.orm import sessionmaker

from .models import MODEL_BY_TABLE, Base
from .modules.utils import camel_to_snake

TIMESTAMP_DIVISOR = 1_000

logger = logging.getLogger(__name__)


class Database:

    def __init__(self, db_type: str, host: str, port: int, user: str, password: str, name: str, schema: str):
        self._type = db_type
        self._schema = schema
        self._url = self._build_url(db_type, host, port, user, password, name)
        self._engine = create_engine(self._url)
        self._session_factory = sessionmaker(bind=self._engine)

    def init_tables(self):
        Base.metadata.create_all(self._engine)
        logger.info("Database tables initialized")

    def _build_url(self, db_type: str, host: str, port: int, user: str, password: str, name: str) -> str:
        if db_type == "postgres":
            return f"postgresql://{user}:{password}@{host}:{port}/{name}"
        elif db_type == "sqlite":
            return f"sqlite:///{name}"
        raise ValueError(f"Unsupported database type: {db_type}")

    def session(self):
        return self._session_factory()

    def insert(self, data: pd.DataFrame, table_name: str, json_columns: Optional[list] = None):
        if len(data) == 0:
            return

        if self._type == "postgres":
            with self._engine.begin() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self._schema}"))

        model = MODEL_BY_TABLE.get(table_name)
        if model is not None:
            self._insert_with_model(data, table_name, model)
            return

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
            logger.warning(f"Duplicate rows skipped in {table_name}")

    def _insert_with_model(self, data: pd.DataFrame, table_name: str, model):
        data.columns = [camel_to_snake(column) for column in data.columns]

        table = model.__table__
        model_columns = set(table.columns.keys())
        drop_columns = [column for column in data.columns if column not in model_columns]
        if drop_columns:
            logger.warning(
                f"Dropping non-model column(s) from {table_name}: {drop_columns}"
            )
            data = data.drop(columns=drop_columns)

        if len(data) == 0:
            return

        timestamp_columns = {
            column.name for column in table.columns if isinstance(column.type, DateTime)
        }
        column_to_attribute = {
            attribute.expression.name: attribute.key
            for attribute in model.__mapper__.column_attrs
        }

        rows = []
        for record in data.to_dict("records"):
            kwargs = {}
            for key, value in record.items():
                if key not in column_to_attribute:
                    continue
                if isinstance(value, (dict, list)):
                    continue
                if pd.isna(value):
                    value = None
                elif key in timestamp_columns and isinstance(value, (int, float)):
                    value = datetime.datetime.fromtimestamp(value / TIMESTAMP_DIVISOR)
                kwargs[column_to_attribute[key]] = value
            rows.append(model(**kwargs))

        session = self._session_factory()
        try:
            session.add_all(rows)
            session.commit()
        except IntegrityError:
            session.rollback()
            logger.warning(f"Duplicate rows skipped in {table_name}")
        finally:
            session.close()

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