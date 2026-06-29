import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import (
    Dataset,
    Conversation,
    Message,
    QuestionAudit,
    WorkspaceDataset,
)
from domain.dataset import AskRequest
from graph.runner import run_agent
from services.cleaning import clean_dataframe
from services.profiling import profile_csv

logger = logging.getLogger("api.datasets")

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

UPLOAD_DIR = Path("./data/uploads")


def _is_csv(file: UploadFile) -> bool:
    name = (file.filename or "").lower()
    if name.endswith(".csv"):
        return True
    ctype = (file.content_type or "").lower()
    return ctype in ("text/csv", "application/csv", "application/vnd.ms-excel")


def _is_xlsx(file: UploadFile) -> bool:
    name = (file.filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return True
    ctype = (file.content_type or "").lower()
    return ctype in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _sanitize_table_name(raw: str) -> str:
    """Derive a python-safe identifier from an arbitrary sheet/file name.

    Lowercases, replaces non-alphanumerics with ``_``, and ensures it does not
    start with a digit. Empty/invalid input falls back to ``df``.
    """
    cleaned = re.sub(r"\W+", "_", (raw or "").strip().lower()).strip("_")
    if not cleaned:
        cleaned = "df"
    if cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned


def _unique_table_name(base: str, taken: set[str]) -> str:
    """Return ``base`` (or ``base2``, ``base3`` ...) not already in ``taken``.

    ``taken`` is mutated to include the chosen name.
    """
    name = base
    n = 2
    while name in taken:
        name = f"{base}{n}"
        n += 1
    taken.add(name)
    return name


def _profile_dataframe(df: pd.DataFrame, store_dir: Path, stem: str) -> tuple[str, dict]:
    """Materialize ``df`` as a CSV in the local store and profile it.

    Returns ``(csv_path_str, profile)``. Writing each sheet/file as its own CSV
    lets the sandbox load every table uniformly via ``read_csv`` and lets
    derived/recipe reuse work the same way for csv and xlsx-sourced tables.
    Reuses the existing ``profile_csv`` so xlsx sheets get the identical profile
    shape (columns / row_count / sample / quality) as CSV uploads.
    """
    csv_path = store_dir / f"{uuid.uuid4().hex}_{stem}.csv"
    df.to_csv(csv_path, index=False)
    profile = profile_csv(str(csv_path))
    return str(csv_path), profile


def _build_csv_dataset(
    *, raw: bytes, filename: str, store_dir: Path, taken: set[str]
) -> dict:
    """Store + clean + profile one CSV upload; return a pending-dataset spec.

    The raw upload is stored untouched; cleaning runs on a copy materialized as
    a separate CSV (the file the sandbox loads). Raises ``api_error`` on parse
    failure.
    """
    stored_path = store_dir / f"{uuid.uuid4().hex}_{filename}"
    stored_path.write_bytes(raw)

    try:
        df = pd.read_csv(str(stored_path))
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("CSV parse failure for %s: %s", stored_path, exc)
        raise api_error("invalid_file", f"The file could not be parsed as CSV: {exc}", 400)
    except Exception as exc:  # pandas raises various subclasses on bad input
        msg = str(exc).lower()
        if any(k in msg for k in ("parse", "csv", "tokeniz", "no columns", "empty", "delimiter")):
            logger.warning("CSV parse failure for %s: %s", stored_path, exc)
            raise api_error("invalid_file", f"The file could not be parsed as CSV: {exc}", 400)
        logger.exception("Unexpected error reading %s", stored_path)
        raise api_error("storage_error", f"Could not read the file: {exc}", 500)

    cleaned, report = clean_dataframe(df)
    cleaned_path, profile = _profile_dataframe(cleaned, store_dir, Path(filename).stem or "data")
    profile["cleaning"] = report

    # The FIRST CSV in a fresh workspace keeps the canonical ``df`` table name
    # (Phase 1/2 backward compatibility — generated code references ``df``).
    # Subsequent files fall back to a filename-derived unique name.
    base = "df" if "df" not in taken else _sanitize_table_name(Path(filename).stem)
    table_name = _unique_table_name(base, taken)
    return {
        "name": filename,
        "file_path": cleaned_path,
        "table_name": table_name,
        "row_count": profile["row_count"],
        "profile_json": profile,
        "source_kind": "csv",
        "source_file": filename,
    }


def _build_xlsx_datasets(
    *, raw: bytes, filename: str, store_dir: Path, taken: set[str]
) -> list[dict]:
    """Store + read every sheet of one xlsx workbook; one dataset spec per sheet.

    Each sheet is cleaned, materialized as its own CSV, and profiled with the
    same profiling service used for CSV uploads, so the sandbox can load every
    sheet uniformly via ``read_csv``. Raises ``api_error`` on an unreadable
    workbook.
    """
    stored_path = store_dir / f"{uuid.uuid4().hex}_{filename}"
    stored_path.write_bytes(raw)

    try:
        sheets = pd.read_excel(str(stored_path), sheet_name=None, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        logger.warning("xlsx parse failure for %s: %s", stored_path, exc)
        raise api_error("invalid_file", f"The workbook could not be read: {exc}", 400)

    if not sheets:
        raise api_error("invalid_file", "The workbook has no sheets.", 400)

    specs: list[dict] = []
    workbook_stem = Path(filename).stem or "workbook"
    for sheet_name, sheet_df in sheets.items():
        cleaned, report = clean_dataframe(sheet_df)
        stem = f"{workbook_stem}_{sheet_name}"
        cleaned_path, profile = _profile_dataframe(cleaned, store_dir, stem)
        profile["cleaning"] = report

        table_name = _unique_table_name(_sanitize_table_name(sheet_name), taken)
        specs.append(
            {
                "name": f"{filename}:{sheet_name}",
                "file_path": cleaned_path,
                "table_name": table_name,
                "row_count": profile["row_count"],
                "profile_json": profile,
                "source_kind": "xlsx_sheet",
                "source_file": filename,
            }
        )
    return specs


@router.post("")
def create_dataset(
    files: list[UploadFile] | None = File(None),
    file: UploadFile | None = File(None),
    conversation_id: int | None = Form(None),
    session: Session = Depends(get_session),
) -> dict:
    # Backward compatible: accept either ``files`` (multi) or a single ``file``.
    uploads: list[UploadFile] = []
    if files:
        uploads.extend(f for f in files if f is not None and f.filename)
    if file is not None and file.filename:
        uploads.append(file)
    if not uploads:
        raise api_error("invalid_file", "No file was provided.", 400)

    for up in uploads:
        if not (_is_csv(up) or _is_xlsx(up)):
            raise api_error(
                "invalid_file", "Only CSV and Excel (.xlsx/.xls) files are supported.", 400
            )

    # If a conversation_id was provided, it must exist — we ADD to its workspace.
    target_conversation: Conversation | None = None
    if conversation_id is not None:
        target_conversation = session.get(Conversation, conversation_id)
        if target_conversation is None:
            raise api_error("not_found", f"Conversation {conversation_id} not found.", 404)

    # Seed the taken-table-name set with any names already bound to the target
    # conversation, so additions never collide with existing workspace tables.
    taken: set[str] = set()
    if target_conversation is not None:
        existing = (
            session.query(WorkspaceDataset)
            .filter(WorkspaceDataset.conversation_id == target_conversation.id)
            .all()
        )
        taken.update(w.table_name for w in existing)

    # Build all dataset specs (store raw bytes, clean, profile). Parse errors
    # propagate as api_error before any DB write.
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.exception("Failed to create upload store")
        raise api_error("storage_error", f"Could not access the file store: {exc}", 500)

    specs: list[dict] = []
    for up in uploads:
        fname = Path(up.filename).name
        try:
            raw = up.file.read()
        except OSError as exc:
            logger.exception("Failed to read upload %s", fname)
            raise api_error("storage_error", f"Could not read the upload: {exc}", 500)
        if _is_xlsx(up):
            specs.extend(
                _build_xlsx_datasets(
                    raw=raw, filename=fname, store_dir=UPLOAD_DIR, taken=taken
                )
            )
        else:
            specs.append(
                _build_csv_dataset(
                    raw=raw, filename=fname, store_dir=UPLOAD_DIR, taken=taken
                )
            )

    # Persist Datasets, then bind into the target conversation's workspace (if
    # one was provided). With no conversation_id, workspace binding is deferred
    # to the first ask (which creates the Conversation lazily).
    try:
        created: list[Dataset] = []
        for spec in specs:
            ds = Dataset(**spec)
            session.add(ds)
            created.append(ds)
        session.flush()

        if target_conversation is not None:
            for ds in created:
                session.add(
                    WorkspaceDataset(
                        conversation_id=target_conversation.id,
                        dataset_id=ds.id,
                        table_name=ds.table_name,
                    )
                )

        session.commit()
        for ds in created:
            session.refresh(ds)
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        logger.exception("Failed to persist datasets")
        raise api_error("storage_error", f"Could not save the dataset(s): {exc}", 500)

    logger.info(
        "dataset.created count=%s conversation_id=%s tables=%s",
        len(created),
        conversation_id,
        [d.table_name for d in created],
    )

    items = [
        {
            "id": d.id,
            "name": d.name,
            "row_count": d.row_count,
            "table_name": d.table_name,
            "profile": d.profile_json,
        }
        for d in created
    ]

    # Backward-compatible response: a single-dataset upload keeps the original
    # top-level shape (id, name, row_count, profile); ``datasets`` always lists
    # every created row so multi-file/multi-sheet clients see them all.
    data = {"datasets": items}
    if conversation_id is not None:
        data["conversation_id"] = conversation_id
    first = items[0]
    data.update(
        {
            "id": first["id"],
            "name": first["name"],
            "row_count": first["row_count"],
            "table_name": first["table_name"],
            "profile": first["profile"],
        }
    )
    return ok(data)


@router.get("/{dataset_id}")
def get_dataset(dataset_id: int, session: Session = Depends(get_session)) -> dict:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise api_error("not_found", f"Dataset {dataset_id} not found.", 404)
    return ok(
        {
            "id": dataset.id,
            "name": dataset.name,
            "row_count": dataset.row_count,
            "profile": dataset.profile_json,
        }
    )


def _llm_unavailable(error: str | None) -> bool:
    if not error:
        return False
    msg = error.lower()
    return any(
        k in msg
        for k in ("llm_unavailable", "gemini unavailable", "model unavailable", "503", "service unavailable")
    )


def _bind_dataset(
    session: Session, conversation_id: int, dataset: Dataset, taken: set[str]
) -> None:
    """Bind one dataset to the conversation's workspace (idempotent).

    ``taken`` is the set of table names already used in this conversation; it is
    updated with the chosen name. A no-op if this dataset is already bound.
    """
    existing = (
        session.query(WorkspaceDataset)
        .filter(
            WorkspaceDataset.conversation_id == conversation_id,
            WorkspaceDataset.dataset_id == dataset.id,
        )
        .first()
    )
    if existing is not None:
        taken.add(existing.table_name)
        return
    base = dataset.table_name
    table_name = base if base not in taken else _unique_table_name(
        _sanitize_table_name(base), taken
    )
    if base not in taken:
        taken.add(base)
    session.add(
        WorkspaceDataset(
            conversation_id=conversation_id,
            dataset_id=dataset.id,
            table_name=table_name,
        )
    )
    session.flush()


def _ensure_primary_in_workspace(
    session: Session, conversation_id: int, dataset: Dataset
) -> None:
    """Ensure the conversation's primary dataset (and its sibling sheets) are
    bound to the workspace.

    When a multi-sheet xlsx (or multi-file batch) was uploaded WITHOUT a
    conversation_id, the sibling datasets share the primary's ``source_file``
    but were not yet bound to any conversation. On the first ask we bind the
    primary AND every sibling that shares its ``source_file`` and is not already
    in another workspace — so a join question can reach all sheets. Idempotent.
    """
    taken = {
        w.table_name
        for w in session.query(WorkspaceDataset)
        .filter(WorkspaceDataset.conversation_id == conversation_id)
        .all()
    }

    _bind_dataset(session, conversation_id, dataset, taken)

    # Bind sibling datasets from the same upload (same source_file) that are not
    # yet bound to ANY conversation's workspace.
    if dataset.source_file:
        siblings = (
            session.query(Dataset)
            .filter(
                Dataset.source_file == dataset.source_file,
                Dataset.id != dataset.id,
            )
            .all()
        )
        for sib in siblings:
            already_bound = (
                session.query(WorkspaceDataset)
                .filter(WorkspaceDataset.dataset_id == sib.id)
                .first()
            )
            if already_bound is None:
                _bind_dataset(session, conversation_id, sib, taken)


def _workspace_context(
    session: Session, conversation_id: int, primary: Dataset
) -> tuple[dict[str, str], dict]:
    """Return ``(dataset_paths, profile)`` spanning the conversation's workspace.

    ``dataset_paths`` maps each workspace ``table_name`` -> file path; ``profile``
    is the primary dataset's profile augmented with a ``tables`` sub-key holding
    every workspace table's profile, so the agent sees all schemas. When the
    conversation has no workspace rows (legacy), this is the single primary
    dataset {table_name: file_path} with its profile unchanged.
    """
    rows = (
        session.query(WorkspaceDataset)
        .filter(WorkspaceDataset.conversation_id == conversation_id)
        .order_by(WorkspaceDataset.id)
        .all()
    )

    if not rows:
        return {primary.table_name: primary.file_path}, primary.profile_json

    dataset_paths: dict[str, str] = {}
    tables: dict[str, dict] = {}
    for w in rows:
        ds = session.get(Dataset, w.dataset_id)
        if ds is None:
            continue
        dataset_paths[w.table_name] = ds.file_path
        tables[w.table_name] = ds.profile_json

    # Base the profile on the primary dataset's profile, but expose every
    # table's schema under "tables" so the write_code prompt sees all of them.
    base = dict(primary.profile_json or {})
    base["tables"] = tables
    return dataset_paths, base


@router.post("/{dataset_id}/ask")
def ask(
    dataset_id: int,
    req: AskRequest,
    session: Session = Depends(get_session),
) -> dict:
    question = (req.question or "").strip()
    if not question:
        raise api_error("invalid_question", "The question must not be empty.", 400)

    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise api_error("not_found", f"Dataset {dataset_id} not found.", 404)

    started = time.monotonic()

    try:
        # Resolve / create the conversation.
        if req.conversation_id is None:
            conversation = Conversation(dataset_id=dataset_id, title=question[:60])
            session.add(conversation)
            session.flush()
            # Lazily bind the primary dataset into the workspace so a fresh
            # single-dataset conversation also has a WorkspaceDataset row.
            _ensure_primary_in_workspace(session, conversation.id, dataset)
        else:
            conversation = session.get(Conversation, req.conversation_id)
            if conversation is None:
                raise api_error("not_found", f"Conversation {req.conversation_id} not found.", 404)
            _ensure_primary_in_workspace(session, conversation.id, dataset)

        # Prior turns for conversational memory (before adding the new user turn).
        prior_messages = (
            session.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.created_at, Message.id)
            .all()
        )
        history = [{"role": m.role, "content": m.content} for m in prior_messages]

        # Persist the user question.
        user_msg = Message(conversation_id=conversation.id, role="user", content=question)
        session.add(user_msg)

        # Create the audit row and flush to obtain its id.
        audit = QuestionAudit(
            conversation_id=conversation.id,
            dataset_id=dataset_id,
            question=question,
            status="completed",
            steps_json=[],
            step_count=0,
            tokens_used=0,
        )
        session.add(audit)
        session.flush()
        audit_id = audit.id
        conversation_id = conversation.id

        # Build dataset_paths + the per-table profile context from ALL datasets
        # in this conversation's workspace, so generated pandas can reference
        # every table by name and JOIN across them. Fall back to the single
        # primary dataset (legacy path) if no workspace rows exist.
        dataset_paths, run_profile = _workspace_context(session, conversation.id, dataset)

        # Commit the user Message + QuestionAudit BEFORE the long agent run so the
        # request-scoped write transaction does not hold the SQLite write lock while
        # run_agent opens its own session to update the audit (avoids "database is
        # locked").
        session.commit()

        result = run_agent(
            dataset_id=dataset_id,
            question=question,
            conversation_id=conversation_id,
            profile=run_profile,
            dataset_paths=dataset_paths,
            history=history,
            audit_id=audit_id,
        )
    except HTTPException:
        # HTTPExceptions (from api_error) must propagate untouched.
        raise
    except Exception as exc:
        session.rollback()
        logger.exception("Unexpected error answering question on dataset %s", dataset_id)
        raise api_error("internal_error", f"The agent run failed: {exc}", 500)

    answer = result.get("answer")
    code = result.get("code")
    result_repr = result.get("result_repr")
    effort = result.get("effort")
    step_count = result.get("step_count") or 0
    status = result.get("status") or "completed"
    tokens_used = result.get("tokens_used") or 0
    error = result.get("error")

    # Re-load the conversation in this (post-commit) session for subsequent writes.
    conversation = session.get(Conversation, conversation_id)

    # Upsert-style refresh of the audit from the return dict (run_agent may also
    # have updated it; re-fetch and set the canonical fields to be safe).
    audit = session.get(QuestionAudit, audit_id)
    if audit is not None:
        audit.answer = answer
        audit.final_code = code
        audit.final_result_repr = result_repr
        audit.effort = effort
        audit.step_count = step_count
        audit.tokens_used = tokens_used
        audit.status = status
        audit.error_message = error
        audit.completed_at = datetime.now(timezone.utc)

    # Persist the assistant message.
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer or "",
        audit_id=audit_id,
    )
    session.add(assistant_msg)

    conversation.updated_at = datetime.now(timezone.utc)

    session.commit()

    latency_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "dataset.ask dataset_id=%s conversation_id=%s audit_id=%s status=%s "
        "step_count=%s tokens=%s latency_ms=%s",
        dataset_id, conversation.id, audit_id, status, step_count, tokens_used, latency_ms,
    )

    # A failed run due to an unavailable model is a 502; budget-exhausted /
    # best-effort failures are NOT errors — they return ok with status="failed".
    if status == "failed" and _llm_unavailable(error):
        raise api_error("llm_unavailable", error or "The language model is unavailable.", 502)

    return ok(
        {
            "conversation_id": conversation.id,
            "audit_id": audit_id,
            "answer": answer,
            "code": code,
            "result_repr": result_repr,
            "effort": effort,
            "step_count": step_count,
            "status": status,
            "tokens_used": tokens_used,
            "chart_spec": result.get("chart_spec"),
            "table": result.get("table"),
            "follow_ups": result.get("follow_ups"),
            "steps": result.get("steps"),
        }
    )
