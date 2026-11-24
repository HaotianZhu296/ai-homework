"""Part 2: load prompts.txt, send every prompt to ChatOpenAI in one batch, print and save results.json."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser

HERE = Path(__file__).resolve().parent
PROMPTS_FILE = HERE / "prompts.txt"
RESULTS_FILE = HERE / "results.json"


def load_prompts(path: Path | str = PROMPTS_FILE) -> list[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def make_llm() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    load_dotenv(HERE / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        base_url=os.environ.get("OPENAI_BASE_URL") or None,  # unset = api.openai.com
        temperature=0,
    )


def parse_response(text: str) -> dict:
    """Read the JSON answer (code fences allowed); keep the raw text if it is not valid JSON."""
    try:
        data = JsonOutputParser().parse(text)
    except OutputParserException:
        return {"error": "response was not valid JSON", "response": text}
    if not isinstance(data, dict):
        return {"error": "response JSON was not an object", "response": text}
    return {key: data.get(key) for key in ("title", "genre", "plot")}


def run_batch(llm: BaseChatModel, prompts: list[str]) -> list[dict]:
    replies = llm.batch(prompts, config={"max_concurrency": 4})
    return [{"prompt": prompt, **parse_response(reply.content)} for prompt, reply in zip(prompts, replies)]


def save_results(results: list[dict], path: Path | str = RESULTS_FILE) -> None:
    Path(path).write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def print_results(results: list[dict]) -> None:
    for item in results:
        if "error" in item:
            print(f"[{item['error']}] {item['prompt']}\n  {item['response']}\n")
            continue
        genre = item["genre"]
        genre = ", ".join(genre) if isinstance(genre, list) else genre
        print(f"{item['title']}  ({genre})\n  {item['plot']}\n")


def main() -> None:
    if not PROMPTS_FILE.exists():
        sys.exit(f"{PROMPTS_FILE.name} not found. Run part1_generate_prompts.py first.")
    prompts = load_prompts()
    print(f"Loaded {len(prompts)} prompts from {PROMPTS_FILE.name}, sending them as one batch...\n")
    results = run_batch(make_llm(), prompts)
    print_results(results)
    save_results(results)
    print(f"Saved {len(results)} results to {RESULTS_FILE.name}")


if __name__ == "__main__":
    main()
