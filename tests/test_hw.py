import pytest
from langchain_core.language_models import FakeListChatModel, FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage

from llm import SQLiteLLMCache, run_query
from tools import TOOLS, number_to_words, square


@pytest.mark.parametrize(
    "n, words",
    [
        (0, "zero"),
        (7, "seven"),
        (13, "thirteen"),
        (40, "forty"),
        (48, "forty-eight"),
        (100, "one hundred"),
        (458, "four hundred fifty-eight"),
        (2048, "two thousand forty-eight"),
        (90210, "ninety thousand two hundred ten"),
        (1_000_001, "one million one"),
        (2_000_000_000, "two billion"),
        (-15, "minus fifteen"),
        (999_999_999_999_999, "nine hundred ninety-nine trillion nine hundred ninety-nine billion "
         "nine hundred ninety-nine million nine hundred ninety-nine thousand nine hundred ninety-nine"),
    ],
)
def test_number_to_words(n, words):
    assert number_to_words(n) == words


@pytest.mark.parametrize("bad", [10**15, 2.5, True, "12"])
def test_number_to_words_rejects_what_it_cannot_spell(bad):
    with pytest.raises((ValueError, TypeError)):
        number_to_words(bad)


def test_square():
    assert square(12) == 144 and square(12.0) == 144 and isinstance(square(12.0), int)
    assert square(-15) == 225 and square(7.5) == 56.25


def test_tools_have_the_names_and_number_argument_the_prompt_refers_to():
    assert set(TOOLS) == {"number_to_words", "square"}
    for t in TOOLS.values():
        assert list(t.args) == ["number"] and t.description


def test_run_query_calls_the_tool_the_model_chose():
    choice = AIMessage(content="", tool_calls=[{"name": "square", "args": {"number": 12}, "id": "1"}])
    model = FakeMessagesListChatModel(responses=[choice])
    _, calls = run_query(model, [HumanMessage("Square 12")], TOOLS)
    assert calls == [{"tool": "square", "args": {"number": 12}, "result": 144}]


def test_run_query_reports_tool_errors_and_unknown_tools():
    choice = AIMessage(content="", tool_calls=[
        {"name": "number_to_words", "args": {"number": 10**15}, "id": "1"},
        {"name": "cube", "args": {"number": 2}, "id": "2"},
    ])
    _, calls = run_query(FakeMessagesListChatModel(responses=[choice]), [HumanMessage("x")], TOOLS)
    assert "too large" in calls[0]["error"] and "unknown tool" in calls[1]["error"]


def test_no_tool_call_means_no_result():
    reply, calls = run_query(FakeMessagesListChatModel(responses=[AIMessage("I can only...")]), [], TOOLS)
    assert calls == [] and reply.content == "I can only..."


def test_cache_answers_a_repeated_prompt_without_calling_the_model_again(tmp_path):
    model = FakeListChatModel(responses=["first", "second"], cache=SQLiteLLMCache(tmp_path / "c.db"))
    assert model.invoke("hello").content == "first"
    assert model.invoke("hello").content == "first"   # cache hit: "second" was never used
    assert model.invoke("other").content == "second"  # a new prompt goes to the model


def test_cache_survives_a_restart_and_keeps_tool_calls(tmp_path):
    path = tmp_path / "c.db"
    choice = AIMessage(content="", tool_calls=[{"name": "square", "args": {"number": 12}, "id": "1"}])
    FakeMessagesListChatModel(responses=[choice], cache=SQLiteLLMCache(path)).invoke("Square 12")

    # A new process: new cache object on the same file, and a model that would answer differently.
    fresh = FakeMessagesListChatModel(responses=[AIMessage("not cached")], cache=SQLiteLLMCache(path))
    reply = fresh.invoke("Square 12")
    assert reply.tool_calls[0]["name"] == "square" and reply.tool_calls[0]["args"] == {"number": 12}
    assert len(SQLiteLLMCache(path)) == 1
