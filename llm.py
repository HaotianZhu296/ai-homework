"""Model setup, the LangChain LLM cache, and the one-call-per-query tool runner."""

from __future__ import annotations

import os
import sqlite3
import sys
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Sequence

from dotenv import load_dotenv
from langchain_core.caches import BaseCache
from langchain_core.globals import set_llm_cache
from langchain_core.load import dumps, loads
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import Generation
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

HERE = Path(__file__).resolve().parent
CACHE_FILE = HERE / ".langchain_cache.db"


class SQLiteLLMCache(BaseCache):
    """A LangChain LLM cache kept in a SQLite file, so results are reused across runs.

    LangChain calls lookup() before every model call with the serialized prompt and a
    string describing the model and its settings (bound tools included). On a hit the
    stored generations are returned and no API request is made; on a miss LangChain
    calls the API and then update(). langchain-core ships only InMemoryCache, which
    forgets everything when the process exits.
    """

    def __init__(self, path: Path | str = CACHE_FILE) -> None:
        self.path = str(path)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS llm_cache ("
                " prompt TEXT NOT NULL, llm_string TEXT NOT NULL, generations TEXT NOT NULL,"
                " PRIMARY KEY (prompt, llm_string))"
            )

    @contextmanager
    def _connect(self):
        """Open, commit on success, and always close (sqlite3's own `with` only commits)."""
        conn = sqlite3.connect(self.path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def lookup(self, prompt: str, llm_string: str) -> Sequence[Generation] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT generations FROM llm_cache WHERE prompt = ? AND llm_string = ?",
                (prompt, llm_string),
            ).fetchone()
        if row is None:
            return None
        with warnings.catch_warnings():  # loads() is marked beta
            warnings.simplefilter("ignore")
            return loads(row[0], allowed_objects="core")

    def update(self, prompt: str, llm_string: str, return_val: Sequence[Generation]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO llm_cache VALUES (?, ?, ?)",
                (prompt, llm_string, dumps(list(return_val))),
            )

    def clear(self, **kwargs: Any) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM llm_cache")

    def __len__(self) -> int:
        with self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]


def enable_cache(path: Path | str = CACHE_FILE) -> SQLiteLLMCache:
    cache = SQLiteLLMCache(path)
    set_llm_cache(cache)  # every chat model now checks this cache first
    return cache


def make_llm():
    from langchain_openai import ChatOpenAI

    load_dotenv(HERE / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        base_url=os.environ.get("OPENAI_BASE_URL") or None,  # unset = api.openai.com
        temperature=0,
    )


def run_query(
    llm_with_tools: Runnable, messages: list[BaseMessage], tools: dict[str, BaseTool]
) -> tuple[AIMessage, list[dict]]:
    """Call the model once, then run whichever tool(s) it chose.

    Returns the model's message and one record per tool call: name, args, and the
    tool's result (or the error it raised, so one bad call does not stop the run).
    """
    reply: AIMessage = llm_with_tools.invoke(messages)
    calls = []
    for call in reply.tool_calls:
        record = {"tool": call["name"], "args": call["args"]}
        selected = tools.get(call["name"])
        if selected is None:
            record["error"] = f"unknown tool {call['name']!r}"
        else:
            try:
                record["result"] = selected.invoke(call["args"])
            except Exception as exc:  # bad arguments or a value the tool rejects
                record["error"] = str(exc)
        calls.append(record)
    return reply, calls
