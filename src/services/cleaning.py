"""Light auto-cleaning with a transparency report (Phase 3).

``clean_dataframe`` performs a small set of safe, non-destructive cleaning
steps on a loaded DataFrame and returns the cleaned copy plus a human-readable
report of every assumption it made. The cleaning is deliberately conservative:
it only removes wholly-empty rows/columns and normalizes whitespace in headers
(and trims surrounding whitespace in string cells). It NEVER fills, drops, or
coerces real values, and it NEVER mutates the input — the original uploaded
file is left untouched (the caller works on a copy materialized from the raw
upload).

The returned ``report`` is a list of plain-English assumption strings suitable
for surfacing to the user under a dataset's ``profile["cleaning"]`` key
(spec/capabilities/persistent_workspace.md: "Messy files are auto-cleaned with
a transparency report of the assumptions made; originals are never mutated").
"""

from __future__ import annotations

import pandas as pd


def _normalize_header(name) -> str:
    """Collapse internal/edge whitespace in a column header to single spaces.

    Non-string headers (ints from a header-less sheet, etc.) are returned
    unchanged so we never lose positional column identity.
    """
    if not isinstance(name, str):
        return name
    return " ".join(name.split())


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Apply light, safe auto-cleaning to ``df`` and report the assumptions.

    Steps (each only reported when it actually changed something):
      1. Drop rows that are entirely empty (all NaN).
      2. Drop columns that are entirely empty (all NaN).
      3. Normalize whitespace in column headers (trim + collapse runs).
      4. Strip surrounding whitespace from string/object cell values.

    Returns ``(cleaned_copy, report)``. The input ``df`` is never mutated.
    """
    report: list[str] = []

    # Always operate on a copy; the original (and the raw file) stay untouched.
    out = df.copy()

    # 1. Wholly-empty rows.
    before_rows = len(out)
    out = out.dropna(axis=0, how="all")
    dropped_rows = before_rows - len(out)
    if dropped_rows > 0:
        noun = "row" if dropped_rows == 1 else "rows"
        report.append(f"Dropped {dropped_rows} wholly-empty {noun}.")

    # 2. Wholly-empty columns.
    before_cols = list(out.columns)
    out = out.dropna(axis=1, how="all")
    dropped_cols = [c for c in before_cols if c not in list(out.columns)]
    if dropped_cols:
        names = ", ".join(str(c) for c in dropped_cols)
        noun = "column" if len(dropped_cols) == 1 else "columns"
        report.append(f"Dropped {len(dropped_cols)} wholly-empty {noun}: {names}.")

    # 3. Header whitespace normalization.
    renames: dict = {}
    for col in out.columns:
        norm = _normalize_header(col)
        if norm != col:
            renames[col] = norm
    if renames:
        out = out.rename(columns=renames)
        changed = ", ".join(f"'{old}' -> '{new}'" for old, new in renames.items())
        noun = "header" if len(renames) == 1 else "headers"
        report.append(f"Normalized whitespace in {len(renames)} {noun}: {changed}.")

    # 4. Trim surrounding whitespace in object/string cells. Only report when a
    #    real change happened, so a clean file produces no noise.
    stripped_any = False
    for col in out.columns:
        series = out[col]
        if series.dtype == object:
            # Only act on str cells; leave NaN / non-str untouched.
            stripped = series.map(
                lambda v: v.strip() if isinstance(v, str) else v
            )
            if not stripped.equals(series):
                out[col] = stripped
                stripped_any = True
    if stripped_any:
        report.append("Trimmed surrounding whitespace from text values.")

    # Reset the index when rows were removed so downstream positional logic and
    # CSV round-trips stay clean (does not alter any data values).
    if dropped_rows > 0:
        out = out.reset_index(drop=True)

    return out, report
