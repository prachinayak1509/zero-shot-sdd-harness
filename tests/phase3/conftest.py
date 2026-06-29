"""Phase 3 persistent-workspace fixtures.

Mirrors the isolated-DB + real-env-skip pattern from tests/phase2/conftest.py so
the real-Gemini Phase 3 tests run against a throwaway SQLite file (never the
user's ./data/agent.db) and skip cleanly when no Gemini key is present.

CRITICAL: tables are created with ``Base.metadata.create_all`` from
``db.models.Base`` so EVERY column/table the Phase 3 backend slices declare on
the ORM (e.g. the ``workspace_datasets`` table and ``Dataset.recipe_code`` /
``Dataset.source_file``) exists in the throwaway DB. Creating from the live
metadata is equivalent to running the Alembic migrations for the test DB — the
schema always matches the current models, so these tests never drift from the
real schema.

Imports are bare because pytest sets ``pythonpath = ["src"]`` (see pyproject).
"""
import io

import pytest


# ---------------------------------------------------------------------------
# Settings singleton reset — mirror the root conftest so a stale Settings()
# from another test module can't leak the wrong DB URL / key state in here.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    import config.settings as m
    m._settings = None
    yield
    m._settings = None


# ---------------------------------------------------------------------------
# Isolated DB — point db.session at a temp SQLite file and create all tables
# straight from the live ORM metadata. init_db is made a no-op so app startup
# (lifespan) doesn't touch the real DB.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.models import Base
    import db.session as session_module

    db_file = tmp_path / "phase3.db"
    engine = create_engine(f"sqlite:///{db_file}")
    # Create every table/column currently declared on the ORM metadata. This
    # is the test-DB equivalent of running the migrations: the Phase 3
    # workspace_datasets table and any new Dataset columns come along for free.
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    # Expose the temp DB URL so any code re-reading settings stays isolated.
    monkeypatch.setenv("AGENT_DATABASE_URL", f"sqlite:///{db_file}")
    yield engine
    engine.dispose()


# ---------------------------------------------------------------------------
# Real-env guard — these tests MUST call real Gemini. Skip (never stub) when
# the key is genuinely absent from .env / the environment.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _real_env():
    from config.settings import get_settings

    if not get_settings().gemini_api_key:
        pytest.skip("real Gemini key not set in .env (AGENT_GEMINI_API_KEY)")
    yield


# ---------------------------------------------------------------------------
# A small, deterministic single-sheet sales CSV for the session/resume and
# derived-dataset tests. Clean categorical (region) + numeric (amount).
# ---------------------------------------------------------------------------
SALES_CSV_COLUMNS = ["region", "amount"]
SALES_CSV_REGIONS = ["north", "south", "east", "west"]


@pytest.fixture(scope="session")
def sales_csv_path(tmp_path_factory):
    """Write a small, deterministic sales CSV and return its path.

    Small (a few hundred rows) so the real-Gemini round-trips stay quick while
    still giving the agent an obvious group-by to compute.
    """
    import csv
    import random

    path = tmp_path_factory.mktemp("phase3_csv") / "sales.csv"
    rng = random.Random(20260629)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(SALES_CSV_COLUMNS)
        for _ in range(300):
            region = rng.choice(SALES_CSV_REGIONS)
            amount = round(rng.uniform(10.0, 500.0), 2)
            writer.writerow([region, amount])
    return str(path)


# ---------------------------------------------------------------------------
# A real 2-sheet .xlsx workbook generated at fixture time with pandas
# ExcelWriter (openpyxl engine). Sheet "orders" (region, amount) and sheet
# "regions" (region, manager) join on ``region`` — so a "total amount by
# manager" question forces the agent to query BOTH sheets together.
# ---------------------------------------------------------------------------
XLSX_REGIONS = ["north", "south", "east", "west"]
XLSX_MANAGERS = {
    "north": "alice",
    "south": "bob",
    "east": "carol",
    "west": "dave",
}


@pytest.fixture(scope="session")
def multisheet_xlsx_bytes():
    """Return the raw bytes of a deterministic 2-sheet xlsx workbook.

    - sheet ``orders``: columns ``region``, ``amount`` over many rows.
    - sheet ``regions``: columns ``region``, ``manager`` (one row per region).

    The two sheets share the ``region`` key so a join question ("total amount
    by manager") cannot be answered from a single sheet alone.
    """
    import random

    import pandas as pd

    rng = random.Random(424242)
    order_rows = []
    for _ in range(120):
        region = rng.choice(XLSX_REGIONS)
        amount = round(rng.uniform(10.0, 500.0), 2)
        order_rows.append({"region": region, "amount": amount})
    orders_df = pd.DataFrame(order_rows, columns=["region", "amount"])
    regions_df = pd.DataFrame(
        [{"region": r, "manager": m} for r, m in XLSX_MANAGERS.items()],
        columns=["region", "manager"],
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        orders_df.to_excel(writer, sheet_name="orders", index=False)
        regions_df.to_excel(writer, sheet_name="regions", index=False)
    return buffer.getvalue()
