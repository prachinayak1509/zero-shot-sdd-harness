"""Sandbox runner subprocess (Sandbox Safety, spec/agent.md).

This module is launched as a SEPARATE subprocess by
``src/sandbox/executor.py`` (never imported in-process). It reads a JSON
payload ``{code, dataset_paths}`` from stdin and executes the LLM-generated
pandas code in a heavily restricted namespace, then writes a JSON result back
on stdout on a single sentinel-prefixed line.

Safety approach (matches spec/agent.md "Sandbox Safety"):
- **Separate process:** runs in its own interpreter so a crash/timeout cannot
  take down the API; the parent kills it after ``timeout_s``.
- **No network:** ``socket.socket`` is monkeypatched to raise BEFORE the
  generated code runs, so any attempt to open a socket (directly or via
  urllib/requests/http) fails immediately.
- **Restricted builtins:** the exec namespace exposes only ``pd`` (pandas), the
  loaded DataFrames by table name, and a small pure-builtin allowlist
  (len, range, min, max, sum, sorted, round, abs, list, dict, set, tuple, str,
  int, float, bool, enumerate, zip, map, filter, any, all). ``open``, ``exec``,
  ``eval``, ``__import__``, ``os``, ``sys``, ``subprocess`` are NOT provided, so
  generated code cannot import modules or touch the filesystem/OS.
- **Dataset access only:** the parent passes ``dataset_paths``; the subprocess
  loads exactly those CSV files into the namespace and nothing else. Phase 1 is
  read-only over the dataset.
- **Result contract:** generated code must assign its answer to ``result``; the
  subprocess serializes ``str(result)`` as a repr plus a JSON-able value when
  possible. Missing or non-serializable ``result`` is reported as an error.
"""

import io
import json
import socket
import sys
import traceback

RESULT_SENTINEL = "__SANDBOX_RESULT__"

# Pure builtins allowlist — no open/exec/eval/__import__/os/sys/subprocess.
_SAFE_BUILTINS = {
    "len": len,
    "range": range,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
    "round": round,
    "abs": abs,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "any": any,
    "all": all,
    "True": True,
    "False": False,
    "None": None,
    "print": print,
}


def _block_network() -> None:
    """Monkeypatch socket.socket to raise, blocking all network egress."""

    def _no_network(*_args, **_kwargs):
        raise RuntimeError("network access is disabled in the sandbox")

    socket.socket = _no_network  # type: ignore[assignment]


def _jsonable(value):
    """Return a JSON-serializable form of ``value`` or None if not possible."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        pass

    # Best-effort conversion for common pandas/numpy types.
    try:
        import pandas as pd  # local import; pandas is always available

        if isinstance(value, pd.DataFrame):
            return json.loads(value.to_json(orient="records"))
        if isinstance(value, pd.Series):
            return json.loads(value.to_json())
        if hasattr(value, "item"):  # numpy scalar
            return _jsonable(value.item())
    except Exception:
        pass

    return None


def _run(payload: dict) -> dict:
    import pandas as pd

    code = payload.get("code") or ""
    dataset_paths = payload.get("dataset_paths") or {}

    # Build the restricted namespace: pandas + loaded DataFrames only.
    safe_globals = {"__builtins__": _SAFE_BUILTINS, "pd": pd}
    for name, path in dataset_paths.items():
        try:
            safe_globals[name] = pd.read_csv(path)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "result_repr": None,
                "result_value": None,
                "stdout": "",
                "error": f"failed to load dataset '{name}': {exc}",
                "traceback": traceback.format_exc(),
            }

    # Block the network before executing untrusted code.
    _block_network()

    stdout_buf = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = stdout_buf
    try:
        exec(code, safe_globals)  # noqa: S102 — restricted namespace by design
    except Exception as exc:  # noqa: BLE001
        sys.stdout = real_stdout
        return {
            "ok": False,
            "result_repr": None,
            "result_value": None,
            "stdout": stdout_buf.getvalue(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        sys.stdout = real_stdout

    if "result" not in safe_globals:
        return {
            "ok": False,
            "result_repr": None,
            "result_value": None,
            "stdout": stdout_buf.getvalue(),
            "error": "generated code did not assign a 'result' variable",
            "traceback": None,
        }

    result = safe_globals["result"]
    return {
        "ok": True,
        "result_repr": str(result),
        "result_value": _jsonable(result),
        "stdout": stdout_buf.getvalue(),
        "error": None,
        "traceback": None,
    }


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        out = {
            "ok": False,
            "result_repr": None,
            "result_value": None,
            "stdout": "",
            "error": f"invalid payload: {exc}",
            "traceback": None,
        }
    else:
        try:
            out = _run(payload)
        except Exception as exc:  # noqa: BLE001 — never let the runner crash silently
            out = {
                "ok": False,
                "result_repr": None,
                "result_value": None,
                "stdout": "",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }

    sys.stdout.write(RESULT_SENTINEL + json.dumps(out))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
