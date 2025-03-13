import logging
import os

import pandas as pd

from src import config

logger = logging.getLogger(config.LOGGER_NAME)


def read_local_events(file_path) -> pd.DataFrame:
    logger.info(f"Reading local events from {file_path}...")
    if os.path.exists(file_path):
        df_events = pd.read_csv(file_path, parse_dates=["start_time"])
    else:
        df_events = pd.DataFrame({
            "organization": [],
            "event_id": [],
            "status": [],
            "start_time": []
        })
        df_events = df_events.astype({
            "organization": str,
            "event_id": str,
            "status": str,
            "start_time": "datetime64[ns]"
        })
    logger.info(f"Retrieved {len(df_events)} event IDs.")
    return df_events


def write_events(file_path: str, df_events: pd.DataFrame) -> None:
    logger.info(f"Writing events to {file_path}...")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    df_events.to_csv(file_path, index=False)
    logger.info(f"{len(df_events)} events written.")
    return


def concat_dfs(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    all_columns = set(df1.columns).union(set(df2.columns))
    df1 = df1.reindex(columns=list(all_columns))
    df2 = df2.reindex(columns=list(all_columns))
    return pd.concat([df1, df2], ignore_index=True)
