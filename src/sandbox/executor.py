"""Sandbox executor — parent side (Sandbox Safety, spec/agent.md).

``sandbox_exec`` launches ``runner_proc.py`` as a SEPARATE subprocess via
``subprocess.run([sys.executable, runner_proc_path], ...)``, passing the code
and dataset paths as a JSON payload on stdin and reading the JSON result back
from stdout (after a sentinel marker). The subprocess is killed after
``timeout_s`` seconds; a timeout becomes a (loop-local) error fed to the retry
loop, never a crash.

The safety guarantees (no network, restricted builtins, dataset-only namespace,
bounded time, result contract) live in ``runner_proc.py`` — this module only
orchestrates the process boundary and decodes the result.
"""

import json
import subprocess
import sys
from pathlib import Path

from sandbox.runner_proc import RESULT_SENTINEL

_RUNNER_PATH = str(Path(__file__).parent / "runner_proc.py")


def _empty_result(error: str) -> dict:
    return {
        "ok": False,
        "result_repr": None,
        "result_value": None,
        "table": None,
        "stdout": "",
        "error": error,
        "traceback": None,
    }


def sandbox_exec(
    code: str,
    dataset_paths: dict[str, str],
    timeout_s: int = 30,
) -> dict:
    """Run LLM-generated pandas in a restricted subprocess.

    Returns ``{ok, result_repr, result_value, table, stdout, error, traceback}``.
    """
    payload = json.dumps({"code": code, "dataset_paths": dataset_paths})

    try:
        completed = subprocess.run(
            [sys.executable, _RUNNER_PATH],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return _empty_result(f"timeout after {timeout_s}s")
    except Exception as exc:  # noqa: BLE001 — subprocess launch failure
        return _empty_result(f"sandbox launch failed: {exc}")

    stdout = completed.stdout or ""
    marker = stdout.rfind(RESULT_SENTINEL)
    if marker == -1:
        # The runner produced no decodable result — surface stderr for context.
        stderr = (completed.stderr or "").strip()
        detail = stderr or "no result returned from sandbox"
        return _empty_result(detail)

    raw_json = stdout[marker + len(RESULT_SENTINEL):]
    try:
        result = json.loads(raw_json)
    except Exception as exc:  # noqa: BLE001
        return _empty_result(f"could not decode sandbox result: {exc}")

    # Preserve any pre-sentinel stdout the generated code emitted.
    leading = stdout[:marker]
    if leading and not result.get("stdout"):
        result["stdout"] = leading
    return result
