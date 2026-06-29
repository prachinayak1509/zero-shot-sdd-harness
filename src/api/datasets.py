import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import Dataset, Conversation, Message, QuestionAudit
from domain.dataset import AskRequest
from graph.runner import run_agent
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


@router.post("")
def create_dataset(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    if file is None or not file.filename:
        raise api_error("invalid_file", "No file was provided.", 400)
    if not _is_csv(file):
        raise api_error("invalid_file", "Only CSV files are supported.", 400)

    filename = Path(file.filename).name

    # Save raw bytes to the local file store.
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        stored_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{filename}"
        raw = file.file.read()
        stored_path.write_bytes(raw)
    except OSError as exc:
        logger.exception("Failed to write upload to local store")
        raise api_error("storage_error", f"Could not store the uploaded file: {exc}", 500)

    path_str = str(stored_path)

    # Profile the CSV. A pandas parse failure is a 400 invalid_file.
    try:
        profile = profile_csv(path_str)
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("CSV parse failure for %s: %s", path_str, exc)
        raise api_error("invalid_file", f"The file could not be parsed as CSV: {exc}", 400)
    except Exception as exc:  # pandas raises various subclasses on bad input
        # Treat empty/unparseable CSV input as invalid_file; anything truly
        # unexpected we surface as storage_error.
        msg = str(exc).lower()
        if any(k in msg for k in ("parse", "csv", "tokeniz", "no columns", "empty", "delimiter")):
            logger.warning("CSV parse failure for %s: %s", path_str, exc)
            raise api_error("invalid_file", f"The file could not be parsed as CSV: {exc}", 400)
        logger.exception("Unexpected error profiling %s", path_str)
        raise api_error("storage_error", f"Could not profile the file: {exc}", 500)

    try:
        dataset = Dataset(
            name=filename,
            file_path=path_str,
            table_name="df",
            row_count=profile["row_count"],
            profile_json=profile,
            source_kind="csv",
        )
        session.add(dataset)
        session.commit()
        session.refresh(dataset)
    except Exception as exc:
        session.rollback()
        logger.exception("Failed to persist Dataset")
        raise api_error("storage_error", f"Could not save the dataset: {exc}", 500)

    logger.info(
        "dataset.created id=%s name=%s row_count=%s", dataset.id, filename, dataset.row_count
    )

    return ok(
        {
            "id": dataset.id,
            "name": dataset.name,
            "row_count": dataset.row_count,
            "profile": profile,
        }
    )


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
        else:
            conversation = session.get(Conversation, req.conversation_id)
            if conversation is None:
                raise api_error("not_found", f"Conversation {req.conversation_id} not found.", 404)

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

        dataset_paths = {dataset.table_name: dataset.file_path}

        # Commit the user Message + QuestionAudit BEFORE the long agent run so the
        # request-scoped write transaction does not hold the SQLite write lock while
        # run_agent opens its own session to update the audit (avoids "database is
        # locked").
        session.commit()

        result = run_agent(
            dataset_id=dataset_id,
            question=question,
            conversation_id=conversation_id,
            profile=dataset.profile_json,
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
            "chart_spec": None,
            "table": None,
            "follow_ups": None,
            "steps": None,
        }
    )
