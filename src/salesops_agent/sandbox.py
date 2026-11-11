"""Run agent-written analysis code over approved CRM data, under strict limits.

Layers, each enforced in code:
1. A syntax check rejects imports, private names, escape attributes, file and
   network functions, and dangerous built-ins before anything runs.
2. The code runs in a separate process with a small set of safe built-ins, only
   the approved CRM DataFrames, and network sockets disabled.
3. The process is terminated if it exceeds the time limit, and output is capped.
"""

import ast
import contextlib
import io
import multiprocessing
from typing import Any

APPROVED_DATASETS = ("accounts", "opportunities", "activities", "support_tickets", "product_usage")

BLOCKED_CALLS = frozenset(
    {
        "open", "eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr",
        "globals", "locals", "vars", "dir", "input", "breakpoint", "help", "type",
        "object", "super", "exit", "quit", "memoryview", "classmethod", "staticmethod",
    }
)  # fmt: skip

# Attributes that reach frames, code objects, or the interpreter without a leading "_".
BLOCKED_ATTRIBUTE_PREFIXES = ("_", "gi_", "cr_", "ag_", "f_", "tb_", "co_", "read_", "to_")
BLOCKED_ATTRIBUTES = frozenset({"eval", "query", "format", "format_map", "pipe", "style"})
ALLOWED_TO_ATTRIBUTES = frozenset({"to_dict", "to_list", "to_string", "to_frame"})

SAFE_BUILTINS = (
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "isinstance", "len",
    "list", "max", "min", "range", "round", "set", "sorted", "str", "sum", "tuple", "zip",
)  # fmt: skip


def validate_code(code: str) -> tuple[bool, str]:
    """Check the code without running it. Returns (is_safe, reason)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"syntax error: {exc.msg}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            return False, "imports are not allowed"
        if isinstance(node, ast.Name) and (node.id.startswith("_") or node.id in BLOCKED_CALLS):
            return False, f"blocked name: {node.id}"
        if isinstance(node, ast.Attribute):
            name = node.attr
            if name in ALLOWED_TO_ATTRIBUTES:
                continue
            if name in BLOCKED_ATTRIBUTES or name.startswith(BLOCKED_ATTRIBUTE_PREFIXES):
                return False, f"blocked attribute: {name}"
        if isinstance(node, ast.Global | ast.Nonlocal | ast.ClassDef | ast.AsyncFunctionDef):
            return False, f"blocked statement: {type(node).__name__}"
    return True, ""


def _disable_network() -> None:
    import socket

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise PermissionError("network access is disabled in the sandbox")

    socket.socket = refuse  # type: ignore[assignment, misc]
    socket.create_connection = refuse  # type: ignore[assignment]
    socket.getaddrinfo = refuse  # type: ignore[assignment]


def _child(code: str, datasets: dict[str, list[dict[str, Any]]], queue: Any) -> None:
    """Runs in the separate process."""
    import builtins

    import pandas as pd

    _disable_network()
    output = io.StringIO()
    safe_builtins = {name: getattr(builtins, name) for name in SAFE_BUILTINS}
    safe_builtins["print"] = lambda *args, **kwargs: print(*args, file=output)
    namespace = {
        "__builtins__": safe_builtins,
        "to_datetime": pd.to_datetime,
        "Timestamp": pd.Timestamp,
        **{name: pd.DataFrame(records) for name, records in datasets.items()},
    }
    try:
        with contextlib.redirect_stdout(output):
            exec(compile(code, "<sandbox>", "exec"), namespace)  # noqa: S102
        queue.put({"status": "ok", "output": output.getvalue()})
    except Exception as exc:
        queue.put({"status": "error", "error": f"{type(exc).__name__}: {exc}"})


def run_sandboxed(
    code: str,
    datasets: dict[str, list[dict[str, Any]]],
    timeout_seconds: float,
    max_output_chars: int,
) -> dict[str, str]:
    """Validate and run the code. Returns {"status": "ok", "output"} or {"status": "error", "error"}."""
    ok, reason = validate_code(code)
    if not ok:
        return {"status": "error", "error": f"code rejected: {reason}"}
    unapproved = set(datasets) - set(APPROVED_DATASETS)
    if unapproved:
        raise ValueError(f"Datasets not approved for the sandbox: {sorted(unapproved)}")

    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_child, args=(code, datasets, queue), daemon=True)
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        return {"status": "error", "error": f"execution timed out after {timeout_seconds}s"}
    if queue.empty():
        return {"status": "error", "error": "the sandbox process exited without a result"}

    result = queue.get()
    if result["status"] == "ok":
        text = result["output"].strip() or "(no output; use print to show results)"
        if len(text) > max_output_chars:
            text = text[:max_output_chars] + "\n[output truncated]"
        result["output"] = text
    return result
