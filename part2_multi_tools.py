"""Part 2: two tools; the model picks one per query from a single llm.invoke() call."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from llm import enable_cache, make_llm, run_query
from tools import TOOLS

SYSTEM_PROMPT = """You are a number assistant with two tools:
- number_to_words: use it when the user wants a number written out, spelled, or converted to English words.
- square: use it when the user wants a number squared, raised to the power of 2, or multiplied by itself.

For each request:
1. Decide which one tool matches what the user is asking for.
2. Call that tool exactly once, passing the number from the request as a plain number (for example "1,000" becomes 1000).
3. Do not work out the answer yourself; the tool's result is the answer.

If neither tool fits the request, do not call any tool. Reply in one sentence that you can only write numbers in words or square them."""

QUERIES = [
    "Convert 458 to words",
    "Square 12",
    "How do you write 1,000,001 in English?",
    "What is 7.5 squared?",
    "Multiply -15 by itself",
    "What is the capital of France?",
]


def main() -> None:
    enable_cache()  # same LangChain cache as Part 1, so a rerun makes no API calls
    llm_with_tools = make_llm().bind_tools(list(TOOLS.values()))

    for query in QUERIES:
        messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(query)]
        reply, calls = run_query(llm_with_tools, messages, TOOLS)  # one LLM call
        print(f"Query: {query}")
        if not calls:
            print(f"  No tool chosen. Model replied: {reply.content}")
        for call in calls:
            print(f"  LLM chose: {call['tool']}({json.dumps(call['args'])})")
            print(f"  Result:    {call.get('result', 'error: ' + call.get('error', ''))}")
        print()


if __name__ == "__main__":
    main()
