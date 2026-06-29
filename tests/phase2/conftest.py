"""Phase 2 rich-answer fixtures.

Mirrors the isolated-DB + real-env-skip pattern from tests/phase1/conftest.py so
the real-Gemini Phase 2 tests run against a throwaway SQLite file (never the
user's ./data/agent.db) and skip cleanly when no Gemini key is present.

Imports are bare because pytest sets ``pythonpath = ["src"]`` (see pyproject).
"""
import csv
import random

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
# Isolated DB — point db.session at a temp SQLite file and create all tables.
# init_db is made a no-op so app startup (lifespan) doesn't touch the real DB.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.models import Base
    import db.session as session_module

    db_file = tmp_path / "phase2.db"
    engine = create_engine(f"sqlite:///{db_file}")
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
# A real, deterministic CSV with 5000+ rows for the grouping/chart/table/
# follow-up tests. A clear categorical column (region) and a numeric column
# (revenue) give the agent an obvious group-by aggregation to chart and table.
# Some nulls/outliers are seeded so quality flags can also fire on this file.
# ---------------------------------------------------------------------------
SALES_COLUMNS = ["region", "product", "units", "revenue"]
SALES_REGIONS = ["north", "south", "east", "west"]
SALES_PRODUCTS = ["widget", "gadget", "gizmo"]
SALES_ROW_COUNT = 5200


@pytest.fixture(scope="session")
def sales_csv_path(tmp_path_factory):
    """Write a 5000+-row sales CSV to a session tmp dir and return its path.

    Deterministic (seeded) so the aggregated group-by the agent produces is
    stable. ``region`` is a clean four-value categorical (→ a bar chart of
    revenue by region); ``revenue`` is numeric. A handful of blank revenue
    cells and a few extreme outlier revenues are injected so the same fixture
    also exercises null/outlier quality flags.
    """
    path = tmp_path_factory.mktemp("phase2_fixtures") / "sales.csv"
    rng = random.Random(20260629)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(SALES_COLUMNS)
        for i in range(SALES_ROW_COUNT):
            region = rng.choice(SALES_REGIONS)
            product = rng.choice(SALES_PRODUCTS)
            units = rng.randint(1, 500)
            revenue = round(units * rng.uniform(1.5, 40.0), 2)
            # Inject a few blank revenue cells (sparse) every ~400 rows.
            if i % 400 == 17:
                writer.writerow([region, product, units, ""])
                continue
            # Inject a few extreme outliers far above the normal range.
            if i % 900 == 33:
                revenue = round(revenue + 500_000.0, 2)
            writer.writerow([region, product, units, revenue])
    return str(path)


# ---------------------------------------------------------------------------
# A small CSV explicitly crafted so deterministic quality flags fire: one
# numeric column with an obvious outlier and one column that is mostly null.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def quality_csv_path(tmp_path_factory):
    """Write a CSV whose profile MUST surface null_pct + outlier flags.

    - ``amount``: a clean numeric column with one gigantic outlier far outside
      the IQR fence, so ``outlier_count`` for it is >= 1.
    - ``notes``: a sparse column that is blank for most rows, so ``null_pct``
      for it is well above the flag threshold (>0, and in fact > 10%).
    - ``label``: a clean categorical for grouping.
    """
    path = tmp_path_factory.mktemp("phase2_quality") / "quality.csv"
    rng = random.Random(424242)
    rows = 200
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["label", "amount", "notes"])
        for i in range(rows):
            label = rng.choice(["a", "b", "c"])
            # Tight normal distribution of amounts around ~100.
            amount = round(rng.uniform(90.0, 110.0), 2)
            # The notes column is blank for the vast majority of rows (sparse).
            note = f"row-{i}" if i % 5 == 0 else ""
            writer.writerow([label, amount, note])
        # One blatant outlier far above the IQR fence.
        writer.writerow(["a", 1_000_000.0, "outlier-row"])
    return str(path)
