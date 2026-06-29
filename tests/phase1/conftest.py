"""Phase 1 end-to-end fixtures.

Mirrors the isolated-DB + real-env-skip pattern from tests/integration so the
real-Gemini end-to-end test runs against a throwaway SQLite file (never the
user's ./data/agent.db) and skips cleanly when no Gemini key is present.

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

    db_file = tmp_path / "phase1.db"
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
# Real-env guard — the end-to-end test MUST call real Gemini. Skip (never
# stub) when the key is genuinely absent from .env / the environment.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _real_env():
    from config.settings import get_settings

    if not get_settings().gemini_api_key:
        pytest.skip("real Gemini key not set in .env (AGENT_GEMINI_API_KEY)")
    yield


# ---------------------------------------------------------------------------
# A real, deterministic CSV with 5000+ rows. Written to a tmp path with the
# stdlib csv module so the repo carries a generator (no big committed binary)
# but the file is guaranteed to exist when the test runs.
# ---------------------------------------------------------------------------
SALES_COLUMNS = ["region", "product", "units", "revenue"]
SALES_REGIONS = ["north", "south", "east", "west"]
SALES_PRODUCTS = ["widget", "gadget", "gizmo"]
SALES_ROW_COUNT = 5000


@pytest.fixture(scope="session")
def sales_csv_path(tmp_path_factory):
    """Write a 5000-row sales CSV to a session tmp dir and return its path.

    Deterministic (seeded) so the directly-computed reproducibility check in
    the test is stable across runs.
    """
    path = tmp_path_factory.mktemp("phase1_fixtures") / "sales.csv"
    rng = random.Random(20260629)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(SALES_COLUMNS)
        for _ in range(SALES_ROW_COUNT):
            region = rng.choice(SALES_REGIONS)
            product = rng.choice(SALES_PRODUCTS)
            units = rng.randint(1, 500)
            revenue = round(units * rng.uniform(1.5, 40.0), 2)
            writer.writerow([region, product, units, revenue])
    return str(path)
