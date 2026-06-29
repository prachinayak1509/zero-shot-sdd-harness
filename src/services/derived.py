"""Derived-dataset save logic — Phase 3.

A derived dataset is saved as BOTH a reusable FILE (a CSV in the local store)
AND a reproducible code recipe (the pandas that produced it), plus a new
``Dataset`` row profiled like any other dataset. The provided code runs in the
restricted sandbox over the source dataset; its ``table`` result ({columns,
rows}) is reconstructed into a DataFrame and written to disk.
"""

import logging
import uuid
from pathlib import Path

import pandas as pd

from sandbox.executor import sandbox_exec
from services.profiling import profile_csv

logger = logging.getLogger("services.derived")

DERIVED_DIR = Path("./data/derived")


class InvalidCode(Exception):
    """The recipe code errored in the sandbox or produced no table."""


class StorageError(Exception):
    """The derived file or its profile could not be written/computed."""


def _safe_name(name: str) -> str:
    """A filesystem-safe slug for the derived filename."""
    cleaned = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name.strip())
    cleaned = cleaned.strip("_") or "derived"
    return cleaned[:80]


def _table_to_dataframe(table: dict) -> pd.DataFrame:
    """Reconstruct a DataFrame from a sandbox ``{columns, rows}`` table."""
    columns = table.get("columns") or []
    rows = table.get("rows") or []
    return pd.DataFrame(rows, columns=columns)


def save_derived_dataset(
    *,
    source: object,
    name: str,
    code: str,
) -> dict:
    """Run ``code`` over ``source`` in the sandbox and materialize a derived file.

    ``source`` is the source ``Dataset`` ORM row (needs ``table_name`` and
    ``file_path``). Returns a dict ``{file_path, profile, row_count, dataframe}``
    for the caller to persist as a ``Dataset`` row. Raises ``InvalidCode`` when
    the sandbox errors or yields no table, ``StorageError`` on file/profile
    failure.
    """
    dataset_paths = {source.table_name: source.file_path}

    result = sandbox_exec(code, dataset_paths)

    if not result.get("ok"):
        detail = result.get("error") or "the recipe code failed to run"
        logger.warning("derived.invalid_code error=%s", detail)
        raise InvalidCode(detail)

    table = result.get("table")
    if not table or not table.get("columns"):
        raise InvalidCode(
            "the recipe code produced no table; assign a DataFrame/Series to 'result'"
        )

    try:
        df = _table_to_dataframe(table)
    except Exception as exc:  # noqa: BLE001 — malformed table from sandbox
        raise InvalidCode(f"the recipe result could not be tabulated: {exc}")

    # Write the derived rows to a reusable CSV in the local store.
    try:
        DERIVED_DIR.mkdir(parents=True, exist_ok=True)
        file_path = DERIVED_DIR / f"{uuid.uuid4().hex}_{_safe_name(name)}.csv"
        df.to_csv(file_path, index=False)
    except OSError as exc:
        logger.exception("derived.storage_error writing CSV")
        raise StorageError(f"could not write the derived file: {exc}")

    path_str = str(file_path)

    # Profile the derived file exactly like any uploaded dataset.
    try:
        profile = profile_csv(path_str)
    except Exception as exc:  # noqa: BLE001
        logger.exception("derived.storage_error profiling derived file")
        raise StorageError(f"could not profile the derived file: {exc}")

    logger.info(
        "derived.saved name=%s file=%s row_count=%s",
        name, path_str, profile["row_count"],
    )

    return {
        "file_path": path_str,
        "profile": profile,
        "row_count": profile["row_count"],
    }
