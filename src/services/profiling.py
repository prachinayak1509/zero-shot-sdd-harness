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

# Quality thresholds (deterministic, no LLM).
NULL_PCT_FLAG_THRESHOLD = 10.0  # flag a column when more than this % is missing
HIGH_CARDINALITY_RATIO = 0.9  # non-numeric column nearly all-unique
HIGH_CARDINALITY_MIN_ROWS = 50  # only meaningful on reasonably large columns
MAX_DATASET_NOTES = 3


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


def _count_iqr_outliers(series: pd.Series) -> int:
    """Count values outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR] for numeric columns.

    Returns 0 for non-numeric columns, empty/tiny columns, or a zero/undefined
    IQR (e.g. constant or near-constant columns). Never raises.
    """
    try:
        if not ptypes.is_numeric_dtype(series):
            return 0
        if ptypes.is_bool_dtype(series):
            return 0  # booleans are categorical for outlier purposes
        clean = series.dropna()
        if len(clean) < 4:
            return 0  # too few points for a meaningful quartile spread
        q1 = clean.quantile(0.25)
        q3 = clean.quantile(0.75)
        iqr = q3 - q1
        if not (iqr > 0) or math.isnan(iqr):
            return 0  # zero/undefined IQR: no outliers definable
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return int(((clean < lower) | (clean > upper)).sum())
    except (TypeError, ValueError):
        return 0


def _column_flags(
    series: pd.Series,
    *,
    null_pct: float,
    outlier_count: int,
    row_count: int,
) -> list[str]:
    """Build a short list of human-readable quality flags for one column.

    Deterministic and defensive: any sub-computation that fails is skipped
    rather than raising, matching the "flag what computed, continue" contract.
    """
    flags: list[str] = []

    if null_pct > NULL_PCT_FLAG_THRESHOLD:
        flags.append(f"{null_pct:.1f}% missing")

    if outlier_count > 0:
        noun = "outlier" if outlier_count == 1 else "outliers"
        flags.append(f"{outlier_count} {noun}")

    try:
        non_null = series.dropna()
        unique_count = int(non_null.nunique())
        if len(non_null) > 0 and unique_count == 1:
            flags.append("constant")
        elif (
            not ptypes.is_numeric_dtype(series)
            and row_count >= HIGH_CARDINALITY_MIN_ROWS
            and unique_count / row_count > HIGH_CARDINALITY_RATIO
        ):
            flags.append("high cardinality")
    except (TypeError, ValueError):
        pass

    return flags


def _dataset_quality(columns: list[dict]) -> dict:
    """Summarize per-column flags into a dataset-level quality object.

    ``total_flags`` is the count of all column flags; ``notes`` are 0-3 short,
    deterministic observations highlighting the most notable issues.
    """
    total_flags = sum(len(col.get("flags", [])) for col in columns)

    notes: list[str] = []
    # Surface missing-data columns first (descending by null %), then outliers.
    missing_cols = sorted(
        (c for c in columns if c.get("null_pct", 0) > NULL_PCT_FLAG_THRESHOLD),
        key=lambda c: c.get("null_pct", 0),
        reverse=True,
    )
    for col in missing_cols:
        if len(notes) >= MAX_DATASET_NOTES:
            break
        notes.append(
            f"Column '{col['name']}' has {col['null_pct']:.0f}% missing values"
        )

    outlier_cols = sorted(
        (c for c in columns if c.get("outlier_count", 0) > 0),
        key=lambda c: c.get("outlier_count", 0),
        reverse=True,
    )
    for col in outlier_cols:
        if len(notes) >= MAX_DATASET_NOTES:
            break
        n = col["outlier_count"]
        noun = "outlier" if n == 1 else "outliers"
        notes.append(f"Column '{col['name']}' has {n} {noun}")

    return {"total_flags": int(total_flags), "notes": notes}


def profile_csv(file_path: str) -> dict:
    """Load a CSV and compute its profile.

    Returns ``{"columns": [...], "row_count": int, "sample": [...],
    "quality": {...}}`` where each column is ``{"name", "dtype", "min", "max",
    "null_count", "null_pct", "outlier_count", "flags"}`` and ``quality`` is a
    dataset-level ``{"total_flags": int, "notes": [...]}`` summary. All
    quality fields are computed deterministically (no LLM); odd input degrades
    (flag what computed, continue) rather than raising.
    """
    df = pd.read_csv(file_path)
    row_count = int(len(df))

    columns = []
    for name in df.columns:
        series = df[name]
        col_min, col_max = _column_range(series)
        null_count = int(series.isna().sum())
        null_pct = round(null_count / row_count * 100, 1) if row_count else 0.0
        outlier_count = _count_iqr_outliers(series)
        flags = _column_flags(
            series,
            null_pct=null_pct,
            outlier_count=outlier_count,
            row_count=row_count,
        )
        columns.append(
            {
                "name": str(name),
                "dtype": str(series.dtype),
                "min": col_min,
                "max": col_max,
                "null_count": null_count,
                "null_pct": null_pct,
                "outlier_count": outlier_count,
                "flags": flags,
            }
        )

    sample_df = df.head(SAMPLE_ROWS)
    sample = [
        {str(col): _to_jsonable(val) for col, val in row.items()}
        for row in sample_df.to_dict(orient="records")
    ]

    return {
        "columns": columns,
        "row_count": row_count,
        "sample": sample,
        "quality": _dataset_quality(columns),
    }
