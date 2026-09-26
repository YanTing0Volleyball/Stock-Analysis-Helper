"""本機 CSV 讀寫，用於離線回測與快取。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..schema import standardize_ohlcv


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    return standardize_ohlcv(pd.read_csv(path))


def save_ohlcv_csv(df: pd.DataFrame, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index_label="date")
