"""Multi-turn chatbot built on the Chat Completions API (Parts 2 and 3).

`ChatSession` keeps the whole conversation in `messages` (system prompt first,
then alternating user/assistant turns) and sends it with every request, which
is what lets the model answer follow-up questions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

# Part 2: the system prompt given in the assignment.
BASE_PROMPT = "You are a friendly assistant who helps users learn programming."

# Part 3: the same role, plus instructions for citing sources.
CITATION_PROMPT = """You are a friendly assistant who helps users learn programming.

How to answer:
- Explain concepts clearly for a learner. Use short code examples when they help, and keep them correct and runnable.
- Build on earlier questions in this conversation instead of repeating yourself.

Citing sources:
- End every answer with a "Sources" section that lists 1 to 3 sources supporting it.
- Prefer real, authoritative sources: official documentation (for example docs.python.org, developer.mozilla.org), well-known books, or standards. Give the title and, when you know it, the URL.
- Never present an invented source as real. If you cannot point to a real source you are confident exists, you may give an illustrative one, but label it "(fictional example)".
- Format each source on its own line as: [n] Title — URL or publisher.

Example of the ending:
Sources:
[1] The Python Tutorial: More Control Flow Tools — https://docs.python.org/3/tutorial/controlflow.html
[2] "Learning Python" by Mark Lutz — O'Reilly Media"""

LOG_FILE = Path(__file__).resolve().parent / "chat_log.txt"


def log_exchange(question: str, answer: str, path: Path | str = LOG_FILE) -> None:
    """Append one question/answer pair to the chat log (Part 3)."""
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{stamp}]\nQ: {question}\nA: {answer}\n{'-' * 60}\n")


class ChatSession:
    def __init__(self, client, model: str, system_prompt: str = BASE_PROMPT, log_path: Path | str | None = None):
        self.client = client
        self.model = model
        self.system_prompt = system_prompt
        self.log_path = log_path
        self.messages: list[dict] = [{"role": "system", "content": system_prompt}]

    def ask(self, question: str) -> str:
        self.messages.append({"role": "user", "content": question})
        try:
            response = self.client.chat.completions.create(model=self.model, messages=self.messages)
        except Exception:
            self.messages.pop()  # keep the history consistent if the call fails
            raise
        answer = response.choices[0].message.content or ""
        self.messages.append({"role": "assistant", "content": answer})
        if self.log_path:
            log_exchange(question, answer, self.log_path)
        return answer

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": self.system_prompt}]

    @property
    def turns(self) -> int:
        return sum(m["role"] == "user" for m in self.messages)


def run_cli(system_prompt: str, log_path: Path | str | None, title: str) -> None:
    """Interactive loop shared by part2_chatbot.py and part3_chatbot.py."""
    from llm_client import get_model, make_client

    session = ChatSession(make_client(), get_model(), system_prompt, log_path)
    print(f"{title}  (model: {session.model})")
    print("Ask as many questions as you like. Commands: /reset to start over, /quit to exit.")
    if log_path:
        print(f"Every question and answer is saved to {Path(log_path).name}.")
    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"/quit", "/exit", "quit", "exit"}:
            break
        if question.lower() == "/reset":
            session.reset()
            print("(conversation cleared)")
            continue
        try:
            answer = session.ask(question)
        except Exception as exc:  # network or API errors: report and keep the session going
            print(f"[error] {exc}")
            continue
        print(f"\nAssistant: {answer}")
    print("Goodbye!")
