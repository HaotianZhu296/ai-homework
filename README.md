# HW1-3: LLM Tools with LangChain

Two Python functions, number to English words and square of a number, are turned into LangChain tools and bound to a chat model. The model reads a request, picks a tool and its argument, and the program runs that tool. LLM results are cached by LangChain, so a repeated request does not call the API again, even in a later run.

`ChatOpenAI` reads its key, base URL and model from `.env`, so it works with OpenAI or any OpenAI-compatible endpoint. The runs shown here used DeepSeek (`deepseek-chat`). To use OpenAI instead, set `OPENAI_API_KEY=sk-...`, remove `OPENAI_BASE_URL`, and set `OPENAI_MODEL=gpt-4o-mini`.

| File | What it does |
|---|---|
| `tools.py` | `number_to_words()` and `square()`, plus their `@tool` wrappers |
| `llm.py` | `SQLiteLLMCache` (the LangChain cache), `make_llm()`, and `run_query()`: one LLM call, then run the chosen tool |
| `part1_words_tool.py` | Part 1: the words tool bound to the model, with the cache on |
| `part2_multi_tools.py` | Part 2: both tools and a prompt that tells the model which to pick |
| `docs/*.txt` | Console output of the runs below |
| `tests/test_hw.py` | 24 unit tests with fake chat models (no key needed) |

## Setup and running

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env                    # then put your API key in .env

.venv/bin/python part1_words_tool.py
.venv/bin/python part2_multi_tools.py
.venv/bin/python -m pytest
```

Delete `.langchain_cache.db` to clear the cache.

## Part 1: Number to English words tool

### The function

`number_to_words(n)` is written by hand (no library). It splits the number into groups of three digits, spells each group (`four hundred fifty-eight`), and adds the scale word (`thousand`, `million`, `billion`, `trillion`). It follows the style of the assignment's example: no "and", and a hyphen for 21 to 99.

| Input | Output |
|---|---|
| 2048 | two thousand forty-eight |
| 90210 | ninety thousand two hundred ten |
| 1000001 | one million one |
| -15 | minus fifteen |
| 0 | zero |

It works up to 999 trillion. A larger number, a fraction, or a non-number raises an error instead of returning wrong words.

### As an LLM tool

```python
@tool("number_to_words")
def number_to_words_tool(number: int) -> str:
    """Spell out a whole number in English words, e.g. 2048 -> "two thousand forty-eight".
    Use when the user wants a number written, spelled or converted to words."""
```

The `@tool` decorator turns the function into a tool. Its name, the `number: int` argument, and the docstring become the schema the model sees, so the docstring says when to use the tool, not just what it does. `llm.bind_tools([number_to_words_tool])` attaches the schema to every request. The model answers with a tool call such as `number_to_words({"number": 2048})`, and `run_query()` runs the tool with those arguments.

### LangChain caching

`enable_cache()` calls `set_llm_cache(...)`, which turns on caching for every LangChain chat model. Before each model call, LangChain looks up the prompt together with a string that describes the model and its settings, including the bound tools. On a hit it returns the stored reply and makes no request. On a miss it calls the API and stores the reply.

langchain-core only ships `InMemoryCache`, which is lost when the program exits. The SQLite cache used to live in `langchain-community`, which is being sunset. So `llm.py` has a small `SQLiteLLMCache` built on LangChain's `BaseCache` interface. It saves replies with LangChain's own serializer, so tool calls are kept intact. The cache is stored in `.langchain_cache.db`, and results are reused across runs.

First run ([docs/part1_first_run.txt](docs/part1_first_run.txt)). The repeated query comes back from the cache:

```
Direct function call: number_to_words(2048) -> 'two thousand forty-eight'

LLM cache: .langchain_cache.db (0 stored results)

Query: Convert 2048 to words
  LLM:    0.81s (API call, now cached)
  Tool:   number_to_words({'number': 2048})
  Result: two thousand forty-eight

Query: Convert 2048 to words
  LLM:    0.00s (reused from cache, no API call)
  Tool:   number_to_words({'number': 2048})
  Result: two thousand forty-eight

Query: Write 90210 in English words
  LLM:    1.14s (API call, now cached)
  Tool:   number_to_words({'number': 90210})
  Result: ninety thousand two hundred ten
```

On the second run of the script, every query is a cache hit ([docs/part1_second_run.txt](docs/part1_second_run.txt)):

```
LLM cache: .langchain_cache.db (2 stored results)

Query: Convert 2048 to words
  LLM:    0.00s (reused from cache, no API call)
...
Query: Write 90210 in English words
  LLM:    0.00s (reused from cache, no API call)
```

"API call" or "cache" is not guessed from the timing. The script counts the rows in the cache before and after each call, and a new row means the API was called.

## Part 2: Multiple tools

`square(x)` returns `x * x`. A whole-number input gives a whole-number result (`12 -> 144`, not `144.0`).

Both tools are bound with `llm.bind_tools([number_to_words_tool, square_tool])`. Each query is answered with one `llm.invoke()`: the model chooses the tool, the program runs it and prints the tool's result. The tool's output is not sent back to the model for a second call.

### The prompt

```
You are a number assistant with two tools:
- number_to_words: use it when the user wants a number written out, spelled, or converted to English words.
- square: use it when the user wants a number squared, raised to the power of 2, or multiplied by itself.

For each request:
1. Decide which one tool matches what the user is asking for.
2. Call that tool exactly once, passing the number from the request as a plain number (for example "1,000" becomes 1000).
3. Do not work out the answer yourself; the tool's result is the answer.

If neither tool fits the request, do not call any tool. Reply in one sentence that you can only write numbers in words or square them.
```

How the prompt is built:

- **Each tool is described by what the user wants.** Each tool is listed with the phrasings that should trigger it ("spelled", "multiplied by itself"), not just its name, so requests that don't use the exact word still go to the right tool.
- **Arguments must be plain numbers.** "1,000,001" has to reach the tool as `1000001`.
- **The model must not compute the answer itself.** The result comes from the tool, so it is always exact.
- **A fallback for requests that need neither tool.** For an unrelated question the model replies without calling any tool, instead of forcing one.

### Results

The two example queries from the assignment, plus four more that test different phrasings, a comma-formatted number, a decimal, a negative number, and a question no tool fits ([docs/part2_output.txt](docs/part2_output.txt)):

```
Query: Convert 458 to words
  LLM chose: number_to_words({"number": 458})
  Result:    four hundred fifty-eight

Query: Square 12
  LLM chose: square({"number": 12})
  Result:    144

Query: How do you write 1,000,001 in English?
  LLM chose: number_to_words({"number": 1000001})
  Result:    one million one

Query: What is 7.5 squared?
  LLM chose: square({"number": 7.5})
  Result:    56.25

Query: Multiply -15 by itself
  LLM chose: square({"number": -15})
  Result:    225

Query: What is the capital of France?
  No tool chosen. Model replied: I can only write numbers in words or square them, so I can't answer questions about capitals.
```

The model picked the right tool, with the right argument, for all six queries.

If the model names a tool that does not exist, or passes a value the tool rejects (for example a number above 999 trillion), `run_query()` records the error for that call and moves on to the next query.

## Tests

`tests/test_hw.py` uses `FakeListChatModel` and `FakeMessagesListChatModel`, so no key or network is needed. It checks that:
- `number_to_words` handles 13 values, from zero through teens, tens, hundreds and every scale up to 999 trillion, plus negatives;
- `number_to_words` rejects values it cannot spell;
- `square` works for whole, decimal and negative numbers;
- the tools have the names and `number` argument the prompt refers to;
- `run_query` runs the tool the model chose, reports tool errors and unknown tools, and handles a reply with no tool call;
- the cache answers a repeated prompt without calling the model again;
- the cache still works after a restart (a new cache object on the same file) and keeps tool calls intact.
