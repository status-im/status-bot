"""
Minimum code to upload data taken from:
https://github.com/status-im/ift-data-py/blob/master/ift_data/clients/postgres.py
"""

import psycopg2
import pandas as pd
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB

class Postgres:
    
    def __init__(self, username: str, password: str, port: int = 5432, database: str = "data-warehouse", host: str = "data-01.do-ams3.bi.test.status.im"):
        
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
        
        data.to_sql(**params)


    def close(self):
        self.__cursor.close()
        self.__conn.close()