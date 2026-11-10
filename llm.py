"""Run a prompt against Claude through the Claude Code CLI in headless mode.

The CLI is called with ``--system-prompt``, which *replaces* Claude Code's own
system prompt, so the model sees only the prompt under test. ``--tools ""``
removes every built-in tool, so the only tools the model can use are the ones
passed in through an MCP config. ``--setting-sources ""`` ignores local
settings, and each call runs in an empty temporary directory so no project
CLAUDE.md is picked up.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "claude-sonnet-5-5"


@dataclass
class LLMResult:
    text: str
    model: str
    cost_usd: float
    num_turns: int
    duration_ms: int


def run_prompt(
    system_prompt: str,
    user_message: str,
    *,
    model: str = DEFAULT_MODEL,
    mcp_config: dict | None = None,
    allowed_tools: list[str] | None = None,
    max_turns: int = 12,
    timeout: int = 300,
) -> LLMResult:
    cmd = [
        "claude",
        "-p",
        "--setting-sources", "",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--output-format", "json",
        "--model", model,
        "--max-turns", str(max_turns),
        "--tools", "",
        "--system-prompt", system_prompt,
    ]
    if mcp_config is not None:
        cmd += ["--strict-mcp-config", "--mcp-config", json.dumps(mcp_config)]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]

    with tempfile.TemporaryDirectory(prefix="llm-run-") as workdir:
        proc = subprocess.run(
            cmd,
            input=user_message,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
        )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(f"claude CLI failed ({proc.returncode}): {proc.stderr.strip()[:500]}")
    payload = json.loads(proc.stdout)
    if payload.get("is_error"):
        raise RuntimeError(f"claude CLI returned an error: {payload.get('result')}")
    return LLMResult(
        text=payload.get("result", ""),
        model=model,
        cost_usd=float(payload.get("total_cost_usd") or 0.0),
        num_turns=int(payload.get("num_turns") or 0),
        duration_ms=int(payload.get("duration_ms") or 0),
    )
