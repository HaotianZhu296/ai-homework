from types import SimpleNamespace

import pytest

from chatbot import BASE_PROMPT, CITATION_PROMPT, ChatSession, log_exchange


class FakeClient:
    """Stands in for openai.OpenAI: records each request and returns a canned reply."""

    def __init__(self, replies=None, fail=False):
        self.requests = []
        self.replies = list(replies or [])
        self.fail = fail
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages):
        self.requests.append({"model": model, "messages": [dict(m) for m in messages]})
        if self.fail:
            raise RuntimeError("network down")
        content = self.replies.pop(0) if self.replies else f"reply {len(self.requests)}"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_part2_prompt_is_the_one_from_the_assignment():
    assert BASE_PROMPT == "You are a friendly assistant who helps users learn programming."


def test_history_is_sent_with_every_question():
    client = FakeClient(["A list stores items.", "Use append()."])
    chat = ChatSession(client, "test-model")
    chat.ask("What is a list?")
    chat.ask("How do I add to it?")

    second = client.requests[1]["messages"]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
    assert second[0]["content"] == BASE_PROMPT
    assert second[2]["content"] == "A list stores items."
    assert chat.turns == 2 and client.requests[1]["model"] == "test-model"


def test_reset_keeps_only_the_system_prompt():
    chat = ChatSession(FakeClient(), "m", CITATION_PROMPT)
    chat.ask("hi")
    chat.reset()
    assert chat.messages == [{"role": "system", "content": CITATION_PROMPT}]


def test_failed_request_does_not_corrupt_history():
    chat = ChatSession(FakeClient(fail=True), "m")
    with pytest.raises(RuntimeError):
        chat.ask("hello?")
    assert chat.messages == [{"role": "system", "content": BASE_PROMPT}]


def test_citation_prompt_asks_for_labelled_sources():
    assert "Sources" in CITATION_PROMPT and "(fictional example)" in CITATION_PROMPT
    assert CITATION_PROMPT.startswith(BASE_PROMPT)


def test_each_exchange_is_appended_to_the_log(tmp_path):
    log = tmp_path / "chat_log.txt"
    chat = ChatSession(FakeClient(["Paris.", "Berlin."]), "m", log_path=log)
    chat.ask("Capital of France?")
    chat.ask("Capital of Germany?")
    text = log.read_text(encoding="utf-8")
    assert text.count("Q: ") == 2 and "Q: Capital of France?\nA: Paris." in text
    assert "Q: Capital of Germany?\nA: Berlin." in text


def test_log_exchange_handles_multiline_and_unicode(tmp_path):
    log = tmp_path / "log.txt"
    log_exchange("Café?", "Line 1\nLine 2 ✓", log)
    assert "A: Line 1\nLine 2 ✓" in log.read_text(encoding="utf-8")
