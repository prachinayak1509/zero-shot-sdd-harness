"""Dataset profiling service.

``profile_csv`` loads a CSV with pandas and returns a compact, JSON-serializable
profile (columns + dtypes + ranges + null counts, row count, and a bounded
sample) matching the ``profile`` shape in spec/api.md. It is pure and in-memory;
it never mutates the file. Only schema/profile stats and a small sample ever
leave the machine to Gemini — never the full dataset.
"""

import math
from typing import Any

import pandas as pd
from pandas.api import types as ptypes

SAMPLE_ROWS = 20


def _to_jsonable(value: Any) -> Any:
    """Cast numpy/pandas scalars to plain JSON-serializable Python values."""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    # numpy scalars expose .item(); pandas NaT / NA handled here too.
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return _to_jsonable(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _column_range(series: pd.Series) -> tuple[Any, Any]:
    """Return (min, max) for numeric/orderable columns, else (None, None)."""
    if series.dropna().empty:
        return None, None
    if ptypes.is_numeric_dtype(series) or ptypes.is_datetime64_any_dtype(series):
        return _to_jsonable(series.min()), _to_jsonable(series.max())
    return None, None


def profile_csv(file_path: str) -> dict:
    """Load a CSV and compute its profile.

    Returns ``{"columns": [...], "row_count": int, "sample": [...]}`` where each
    column is ``{"name", "dtype", "min", "max", "null_count"}``.
    """
    df = pd.read_csv(file_path)

    columns = []
    for name in df.columns:
        series = df[name]
        col_min, col_max = _column_range(series)
        columns.append(
            {
                "name": str(name),
                "dtype": str(series.dtype),
                "min": col_min,
                "max": col_max,
                "null_count": int(series.isna().sum()),
            }
        )

    sample_df = df.head(SAMPLE_ROWS)
    sample = [
        {str(col): _to_jsonable(val) for col, val in row.items()}
        for row in sample_df.to_dict(orient="records")
    ]

    return {
        "columns": columns,
        "row_count": int(len(df)),
        "sample": sample,
    }
