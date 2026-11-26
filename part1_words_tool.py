"""Part 1: the number-to-words function as an LLM tool, with LangChain caching.

The same query is sent twice. The first call goes to the API and is stored in the
cache; the second is answered from the cache with no API request. Because the cache
is a SQLite file, running the script again reuses every result from the last run.
"""

from __future__ import annotations

import time

from langchain_core.messages import HumanMessage, SystemMessage

from llm import enable_cache, make_llm, run_query
from tools import TOOLS, number_to_words, number_to_words_tool

SYSTEM_PROMPT = (
    "When the user wants a number written in English words, call the number_to_words tool "
    "with that number. Do not spell the number out yourself."
)
QUERIES = ["Convert 2048 to words", "Convert 2048 to words", "Write 90210 in English words"]


def main() -> None:
    print(f"Direct function call: number_to_words(2048) -> {number_to_words(2048)!r}\n")

    cache = enable_cache()
    llm_with_tools = make_llm().bind_tools([number_to_words_tool])
    print(f"LLM cache: {cache.path.rsplit('/', 1)[-1]} ({len(cache)} stored results)\n")

    for query in QUERIES:
        stored_before = len(cache)
        start = time.perf_counter()
        messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(query)]
        reply, calls = run_query(llm_with_tools, messages, TOOLS)
        elapsed = time.perf_counter() - start
        source = "API call, now cached" if len(cache) > stored_before else "reused from cache, no API call"

        print(f"Query: {query}")
        print(f"  LLM:    {elapsed:.2f}s ({source})")
        if not calls:
            print(f"  No tool call. Model said: {reply.content}")
        for call in calls:
            print(f"  Tool:   {call['tool']}({call['args']})")
            print(f"  Result: {call.get('result', 'error: ' + call.get('error', ''))}")
        print()


if __name__ == "__main__":
    main()
