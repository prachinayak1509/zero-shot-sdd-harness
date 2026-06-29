"""Save-derived-dataset endpoint — Phase 3.

``POST /api/datasets/{id}/derived`` runs a provided pandas recipe in the
sandbox over a source dataset and persists the result as BOTH a reusable CSV
file in the local store AND a new ``Dataset`` row (``source_kind="derived"``,
``recipe_code=code``) profiled like any other dataset.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import Dataset
from services.derived import save_derived_dataset, InvalidCode, StorageError

logger = logging.getLogger("api.derived")

# Same prefix as datasets so the path is /api/datasets/{id}/derived; the
# datasets router owns the other routes — these are disjoint operations.
router = APIRouter(prefix="/api/datasets", tags=["derived"])


class DerivedRequest(BaseModel):
    name: str
    code: str
    conversation_id: int | None = None


def _set_if_has(obj: object, attr: str, value: object) -> None:
    """Set ``attr`` only if the model actually declares that column.

    Defensive: ``Dataset.recipe_code`` / ``source_file`` are added by the
    db-multifile slice's migration 0003. This slice must not hard-depend on
    those columns existing at import time, so we set them only when present.
    """
    if hasattr(obj, attr):
        setattr(obj, attr, value)


@router.post("/{dataset_id}/derived")
def create_derived(
    dataset_id: int,
    req: DerivedRequest,
    session: Session = Depends(get_session),
) -> dict:
    name = (req.name or "").strip()
    code = (req.code or "").strip()
    if not name:
        raise api_error("invalid_code", "A name for the derived dataset is required.", 400)
    if not code:
        raise api_error("invalid_code", "The recipe code must not be empty.", 400)

    source = session.get(Dataset, dataset_id)
    if source is None:
        raise api_error("not_found", f"Dataset {dataset_id} not found.", 404)

    # Run the recipe in the sandbox + materialize the derived CSV + profile.
    try:
        derived = save_derived_dataset(source=source, name=name, code=code)
    except InvalidCode as exc:
        raise api_error("invalid_code", f"The recipe could not be run: {exc}", 400)
    except StorageError as exc:
        raise api_error("storage_error", f"Could not store the derived dataset: {exc}", 500)
    except Exception as exc:  # noqa: BLE001 — unexpected sandbox/IO failure
        logger.exception("Unexpected error saving derived dataset for %s", dataset_id)
        raise api_error("storage_error", f"Could not store the derived dataset: {exc}", 500)

    # Persist the new derived Dataset row (recipe + profile).
    try:
        dataset = Dataset(
            name=name,
            file_path=derived["file_path"],
            table_name="df",
            row_count=derived["row_count"],
            profile_json=derived["profile"],
            source_kind="derived",
        )
        # Columns added by migration 0003 (db-multifile slice) — set defensively.
        _set_if_has(dataset, "recipe_code", code)
        _set_if_has(dataset, "source_file", source.file_path)
        session.add(dataset)
        session.commit()
        session.refresh(dataset)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.exception("Failed to persist derived Dataset")
        raise api_error("storage_error", f"Could not save the derived dataset: {exc}", 500)

    logger.info(
        "derived.created id=%s name=%s source_id=%s row_count=%s",
        dataset.id, name, dataset_id, dataset.row_count,
    )

    return ok(
        {
            "id": dataset.id,
            "name": dataset.name,
            "file_path": dataset.file_path,
            "recipe": code,
            "row_count": dataset.row_count,
        }
    )
