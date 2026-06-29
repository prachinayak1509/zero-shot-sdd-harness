"""Graph nodes for the data-analysis agent (spec/agent.md "Nodes / Steps").

Each LLM node (plan / write_code / finalize) calls ``LLMClient().call_model``
with a prompt loaded from ``src/prompts/*.md``. A fatal LLM failure (after the
client's own retries) sets ``state['error']`` and routes to ``handle_error``. The
sandbox node (run_code) sets the loop-local ``state['last_error']`` on failure —
that is NOT fatal; ``inspect`` decides whether to retry.
"""

import json
import logging
import re
import time
from pathlib import Path

from config.settings import get_settings
from graph.state import AgentState
from llm.client import LLMClient
from sandbox.executor import sandbox_exec

logger = logging.getLogger("agent.graph")

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_MAX_HISTORY_TURNS = 6
_CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def _estimate_tokens(*texts: str) -> int:
    """Best-effort token estimate (~4 chars/token) when the provider does not
    return usage counts. Never raises."""
    total_chars = sum(len(t or "") for t in texts)
    return max(1, total_chars // 4)


def _recent_history(state: AgentState) -> list[dict]:
    history = state.get("history") or []
    return history[-_MAX_HISTORY_TURNS:]


def _profile_context(state: AgentState) -> str:
    """Compact JSON of schema + stats + bounded sample for prompts."""
    profile = state.get("profile") or {}
    return json.dumps(profile, default=str)[:8000]


def _append_step(state: AgentState, entry: dict) -> list[dict]:
    steps = list(state.get("steps") or [])
    steps.append(entry)
    return steps


def _extract_code(text: str) -> str | None:
    if not text:
        return None
    match = _CODE_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    # No fence — accept raw text only if it looks like code assigning result.
    stripped = text.strip()
    if "result" in stripped:
        return stripped
    return None


def node_plan(state: AgentState) -> AgentState:
    """Classify effort + sketch approach (Gemini)."""
    started = time.monotonic()
    system = _load_prompt("plan.md")
    prompt = (
        f"Dataset profile (schema, stats, sample):\n{_profile_context(state)}\n\n"
        f"Prior conversation turns: {json.dumps(_recent_history(state), default=str)}\n\n"
        f"Question: {state['question']}"
    )
    try:
        raw = LLMClient(model=get_settings().llm_model_fast).call_model(prompt, system=system)
    except Exception as exc:  # noqa: BLE001 — fatal after client retries
        logger.error("plan failed run_id=%s: %s", state.get("run_id"), exc)
        return {
            **state,
            "error": f"llm_unavailable: {exc}",
            "steps": _append_step(
                state, {"node": "plan", "code": None, "result_repr": None,
                         "error": str(exc), "rationale": None, "tokens": 0}
            ),
        }

    effort, approach = _parse_plan(raw)
    tokens = _estimate_tokens(system, prompt, raw)
    logger.info(
        "plan run_id=%s effort=%s latency_ms=%d tokens=%d",
        state.get("run_id"), effort, int((time.monotonic() - started) * 1000), tokens,
    )
    return {
        **state,
        "effort": effort,
        "approach": approach,
        "tokens_used": (state.get("tokens_used") or 0) + tokens,
        "steps": _append_step(
            state, {"node": "plan", "code": None, "result_repr": None,
                    "error": None, "rationale": approach, "tokens": tokens}
        ),
    }


def _parse_plan(raw: str) -> tuple[str, str]:
    """Parse the plan node's JSON; degrade gracefully to 'hard'."""
    text = (raw or "").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            effort = str(obj.get("effort", "hard")).strip().lower()
            if effort not in ("trivial", "hard"):
                effort = "hard"
            approach = str(obj.get("approach", "")).strip() or "Compute the answer directly."
            return effort, approach
        except Exception:  # noqa: BLE001
            pass
    return "hard", text[:200] or "Compute the answer directly."


def node_write_code(state: AgentState) -> AgentState:
    """Generate/refine pandas (Gemini), extract the fenced code block."""
    started = time.monotonic()
    system = _load_prompt("write_code.md")

    table_names = list((state.get("dataset_paths") or {}).keys()) or ["df"]
    parts = [
        f"Dataset profile (schema, stats, sample):\n{_profile_context(state)}",
        f"The DataFrame variable name(s) available: {', '.join(table_names)}",
        f"Approach: {state.get('approach') or ''}",
        f"Prior conversation turns: {json.dumps(_recent_history(state), default=str)}",
        f"Question: {state['question']}",
    ]
    if state.get("last_error"):
        parts.append(
            "Your previous attempt failed. Fix it.\n"
            f"Previous code:\n{state.get('code') or ''}\n"
            f"Error:\n{state.get('last_error')}"
        )
    prompt = "\n\n".join(parts)

    try:
        raw = LLMClient().call_model(prompt, system=system)
    except Exception as exc:  # noqa: BLE001 — fatal after client retries
        logger.error("write_code failed run_id=%s: %s", state.get("run_id"), exc)
        return {
            **state,
            "error": f"llm_unavailable: {exc}",
            "steps": _append_step(
                state, {"node": "write_code", "code": None, "result_repr": None,
                         "error": str(exc), "rationale": None, "tokens": 0}
            ),
        }

    code = _extract_code(raw)
    tokens = _estimate_tokens(system, prompt, raw)
    logger.info(
        "write_code run_id=%s has_code=%s latency_ms=%d tokens=%d",
        state.get("run_id"), code is not None,
        int((time.monotonic() - started) * 1000), tokens,
    )

    if not code:
        # No usable code: feed back into the retry loop as a loop-local error.
        return {
            **state,
            "last_error": "model did not return a usable python code block",
            "tokens_used": (state.get("tokens_used") or 0) + tokens,
            "steps": _append_step(
                state, {"node": "write_code", "code": None, "result_repr": None,
                        "error": "no code block", "rationale": None, "tokens": tokens}
            ),
        }

    return {
        **state,
        "code": code,
        "tokens_used": (state.get("tokens_used") or 0) + tokens,
        "steps": _append_step(
            state, {"node": "write_code", "code": code, "result_repr": None,
                    "error": None, "rationale": "generated pandas", "tokens": tokens}
        ),
    }


def node_run_code(state: AgentState) -> AgentState:
    """Run the generated pandas in the sandbox subprocess (no LLM call)."""
    started = time.monotonic()
    code = state.get("code") or ""
    dataset_paths = state.get("dataset_paths") or {}

    result = sandbox_exec(code, dataset_paths)
    step_count = (state.get("step_count") or 0) + 1
    latency_ms = int((time.monotonic() - started) * 1000)

    if result.get("ok"):
        logger.info(
            "run_code run_id=%s step=%d ok=True latency_ms=%d",
            state.get("run_id"), step_count, latency_ms,
        )
        return {
            **state,
            "last_result": result.get("result_value"),
            "last_result_repr": result.get("result_repr"),
            "last_error": None,
            "step_count": step_count,
            "steps": _append_step(
                state, {"node": "run_code", "code": code,
                        "result_repr": result.get("result_repr"),
                        "error": None, "rationale": "sandbox ok", "tokens": 0}
            ),
        }

    error = result.get("error") or "sandbox execution failed"
    logger.info(
        "run_code run_id=%s step=%d ok=False error=%s latency_ms=%d",
        state.get("run_id"), step_count, error, latency_ms,
    )
    return {
        **state,
        "last_result": None,
        "last_result_repr": None,
        "last_error": error,
        "step_count": step_count,
        "steps": _append_step(
            state, {"node": "run_code", "code": code, "result_repr": None,
                    "error": error, "rationale": "sandbox error", "tokens": 0}
        ),
    }


def node_inspect(state: AgentState) -> AgentState:
    """Deterministic routing-prep (no LLM call). Records a rationale; the actual
    branch is decided by the conditional edge in agent.py."""
    has_error = bool(state.get("last_error"))
    budget_left = (state.get("step_count") or 0) < (state.get("step_budget") or 5)
    if has_error and budget_left:
        rationale = "error present and budget remains — retry write_code"
    elif has_error:
        rationale = "error present but budget exhausted — finalize best-effort"
    else:
        rationale = "valid result — finalize"
    logger.info("inspect run_id=%s %s", state.get("run_id"), rationale)
    return {
        **state,
        "steps": _append_step(
            state, {"node": "inspect", "code": None, "result_repr": None,
                    "error": state.get("last_error"), "rationale": rationale, "tokens": 0}
        ),
    }


def node_finalize(state: AgentState) -> AgentState:
    """Compose the prose answer (Gemini) from the raw result."""
    started = time.monotonic()
    system = _load_prompt("finalize.md")
    prompt = (
        f"Question: {state['question']}\n\n"
        f"Raw computed result: {state.get('last_result_repr')}\n\n"
        f"Code:\n{state.get('code') or ''}\n\n"
        f"Last error (if any): {state.get('last_error') or 'none'}\n\n"
        f"Effort: {state.get('effort')}"
    )
    try:
        answer = LLMClient().call_model(prompt, system=system)
        tokens = _estimate_tokens(system, prompt, answer)
    except Exception as exc:  # noqa: BLE001
        # Finalize should not become a fatal graph error — degrade to a plain
        # answer built from what we have, so the user always gets a response.
        logger.error("finalize llm failed run_id=%s: %s", state.get("run_id"), exc)
        if state.get("last_error"):
            answer = (
                "I was unable to compute a clean result. Last error: "
                f"{state.get('last_error')}. Try rephrasing the question."
            )
        else:
            answer = f"Result: {state.get('last_result_repr')}"
        tokens = 0

    logger.info(
        "finalize run_id=%s latency_ms=%d tokens=%d",
        state.get("run_id"), int((time.monotonic() - started) * 1000), tokens,
    )
    return {
        **state,
        "answer": answer,
        "final_code": state.get("code"),
        "final_result_repr": state.get("last_result_repr"),
        "tokens_used": (state.get("tokens_used") or 0) + tokens,
        "checkpoint": "finalize",
        "steps": _append_step(
            state, {"node": "finalize", "code": state.get("code"),
                    "result_repr": state.get("last_result_repr"),
                    "error": state.get("last_error"), "rationale": "composed answer",
                    "tokens": tokens}
        ),
    }


def node_handle_error(state: AgentState) -> AgentState:
    """Mark the run as failed and terminate (fatal path)."""
    logger.error(
        "handle_error run_id=%s error=%s", state.get("run_id"), state.get("error")
    )
    return {
        **state,
        "checkpoint": "handle_error",
        "steps": _append_step(
            state, {"node": "handle_error", "code": None, "result_repr": None,
                    "error": state.get("error"), "rationale": "fatal", "tokens": 0}
        ),
    }
