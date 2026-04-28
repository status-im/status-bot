"""
Minimum code to upload data taken from:
https://github.com/status-im/ift-data-py/blob/master/ift_data/clients/postgres.py
"""

import psycopg2
import pandas as pd
from typing import Optional, Union
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB

class Postgres:

    def __init__(self, username: str, password: str, port: Union[int, str], database: str, host: str):

        if isinstance(port, str):
            port = int(port)

        self.__params = {
            "host": host,
            "user": username,
            "password": password,
            "port": port,
            "database": database
        }

        self.__url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
        self.__conn: psycopg2.extensions.connection = psycopg2.connect(**self.__params)
        self.__cursor: psycopg2.extensions.cursor = self.__conn.cursor()

    def insert(self, data: pd.DataFrame, table_name: str, schema: str, json_columns: Optional[list] = None):
        """
        Insert the DataFrame in the specified schema > table.
        If the schema / table name does not exist, it will be created.

        Parameters:
            - `data` - the data to be inserted in Postgres
            - `table_name` - the name of the table
            - `schema` - the name of the schema
            - `json_columns` - when creating the table, `dict` columns will be turned into JSON objects in Postgres
        """
        self.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        engine = create_engine(self.__url)

        data.columns = [column.lower() for column in data.columns]

        params = {
            "name": table_name,
            "con": engine,
            "schema": schema,
            "if_exists": "append",
            "index": False
        }
        if json_columns:
            params["dtype"] = {
                json_column: JSONB
                for json_column in json_columns
            }

        # Add new columns as they come
        existing_columns = self.get_columns(schema, table_name)

        if existing_columns:
            for column in data.columns:
                if column in existing_columns:
                    continue
                #  NOTE: New values will have to be transformed
                self.execute(f"ALTER TABLE {schema}.{table_name} ADD COLUMN {column} TEXT")

        data.to_sql(**params)

    def execute(self, query: str):
        """
        Execute queries such as INSERT, UPDATE, DELETE etc.

        Parameters:
            -  `query` - the PostgreSQL query
        """
        self.__execute(query)
        self.__conn.commit()

    def to_pandas(self, query: str, batch_size: int = 50_000, uppercase: bool = True) -> pd.DataFrame:
        """
        Create a DataFrame from the given query

        Parameters:
            - `query` - the PostgreSQL query
            - `batch_size` - how many rows will be fetched at once
            - `uppercase` - if `True` then the columns will be uppercase. If `False` the columns will be lowercase
        Output:
            - DataFrame for the executed query
        """
        self.__execute(query)
        columns = [column.name.upper() if uppercase else column.name.lower() for column in self.__cursor.description]
        chunks = []

        while True:
            rows = self.__cursor.fetchmany(batch_size)
            if not rows:
                break
            chunks.append(pd.DataFrame(rows, columns=columns))

        return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns)

    def close(self):
        self.__cursor.close()
        self.__conn.close()

    def __del__(self):
        self.close()

    def __execute(self, query: str):

        failed = False
        is_closed = bool(self.__conn.closed)

        if is_closed:
            self.__conn: psycopg2.extensions.connection = psycopg2.connect(**self.__params)
            self.__cursor: psycopg2.extensions.cursor = self.__conn.cursor()

        try:
            self.__cursor.execute(query)
        except psycopg2.errors.InFailedSqlTransaction:
            self.__conn.rollback()
            failed = True

        if failed:
            self.__cursor.execute(query)


    def get_columns(self, schema: str, table_name: str) -> list[str]:
        """
        Get the column names in the correct order for the given table.

        Parameters:
            - `table_name` - the name of the table
            - `schema` - the name of the schema

        Output:
            - the table's columns in the correct order
        """
        query = f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = '{table_name}'
        AND table_schema = '{schema}'
        ORDER BY ordinal_position ASC
        """
        return self.to_pandas(query)["COLUMN_NAME"].to_list()
