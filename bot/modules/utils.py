import datetime
import os
import pickle
from hashlib import sha256

import pandas as pd
from typing import Any


def to_sha256_hash(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def to_midnight(timestamp: datetime.datetime) -> datetime.datetime:
    return timestamp.replace(minute=0, second=0, hour=0, microsecond=0)


def save_file(file_path: str, data: Any):
    folder = os.path.dirname(file_path)
    if len(folder) > 0:
        os.makedirs(folder, exist_ok=True)

    if isinstance(data, pd.DataFrame):
        data.to_csv(file_path, index=False)
        return

    with open(file_path, "wb") as f:
        pickle.dump(data, f)
