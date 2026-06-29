"""Saved-session (Conversation) list + detail endpoints — Phase 3.

Powers the saved-sessions sidebar (``GET /api/conversations``) and the resume
view (``GET /api/conversations/{id}``) which reloads a conversation's ordered
turns, each assistant turn carrying its full reconstructed step-trace and the
running per-session token total (the cost meter).
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import Conversation, Message, QuestionAudit

logger = logging.getLogger("api.sessions")

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


@router.get("")
def list_conversations(session: Session = Depends(get_session)) -> dict:
    """List saved sessions for the sidebar, newest activity first.

    Returns ``{id, title, dataset_id, updated_at, message_count}`` per
    conversation, ordered by ``updated_at`` descending.
    """
    # Per-conversation message counts in one grouped query (avoids N+1).
    counts = dict(
        session.query(Message.conversation_id, func.count(Message.id))
        .group_by(Message.conversation_id)
        .all()
    )

    conversations = (
        session.query(Conversation)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .all()
    )

    data = [
        {
            "id": c.id,
            "title": c.title,
            "dataset_id": c.dataset_id,
            "updated_at": _iso(c.updated_at),
            "message_count": int(counts.get(c.id, 0)),
        }
        for c in conversations
    ]
    return ok(data)


def _build_steps(audit: QuestionAudit) -> list[dict]:
    """Reconstruct the FULL ordered trace from ``QuestionAudit.steps_json``.

    Each step is normalized to ``{node, code, result_repr, error, rationale,
    tokens}`` so the step-trace drawer always sees a stable shape even if an
    older audit stored a sparser record. Never raises on a malformed entry.
    """
    raw_steps = audit.steps_json or []
    steps: list[dict] = []
    for entry in raw_steps:
        if not isinstance(entry, dict):
            continue
        steps.append(
            {
                "node": entry.get("node"),
                "code": entry.get("code"),
                "result_repr": entry.get("result_repr"),
                "error": entry.get("error"),
                "rationale": entry.get("rationale"),
                "tokens": entry.get("tokens"),
            }
        )
    return steps


def _audit_payload(audit: QuestionAudit) -> dict:
    """Reconstruct the assistant turn's audit in AskResult shape (Phase 1/2).

    The frontend ``MessageAudit`` type and the live ask response share one
    contract, so a resumed turn must expose the SAME keys. ``code`` /
    ``result_repr`` are renamed from the persisted ``final_code`` /
    ``final_result_repr`` columns. ``chart_spec`` / ``table`` / ``follow_ups``
    were never persisted to ``QuestionAudit`` (only steps/code/result/answer
    are stored), so they are not reconstructable on reload and return ``None``
    — the restored prose + code + step trace still render.
    """
    return {
        "audit_id": audit.id,
        "answer": audit.answer,
        "code": audit.final_code,
        "result_repr": audit.final_result_repr,
        "effort": audit.effort,
        "step_count": audit.step_count,
        "tokens_used": audit.tokens_used,
        "status": audit.status,
        "steps": _build_steps(audit),
        "chart_spec": None,
        "table": None,
        "follow_ups": None,
    }


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: int, session: Session = Depends(get_session)
) -> dict:
    """Reload one conversation with its ordered turns + audits (resume).

    ``session_tokens`` is the SUM of ``tokens_used`` across the conversation's
    audits — the running session total shown live in the cost meter. 404
    ``not_found`` if the conversation does not exist.
    """
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise api_error("not_found", f"Conversation {conversation_id} not found.", 404)

    messages = (
        session.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
        .all()
    )

    # Running session total = sum of tokens across this conversation's audits.
    session_tokens = (
        session.query(func.coalesce(func.sum(QuestionAudit.tokens_used), 0))
        .filter(QuestionAudit.conversation_id == conversation_id)
        .scalar()
    )

    message_payload: list[dict] = []
    for m in messages:
        audit_data = None
        if m.audit_id is not None:
            audit = session.get(QuestionAudit, m.audit_id)
            if audit is not None:
                audit_data = _audit_payload(audit)
        message_payload.append(
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": _iso(m.created_at),
                "audit": audit_data,
            }
        )

    return ok(
        {
            "id": conversation.id,
            "title": conversation.title,
            "dataset_id": conversation.dataset_id,
            "updated_at": _iso(conversation.updated_at),
            "session_tokens": int(session_tokens or 0),
            "messages": message_payload,
        }
    )
