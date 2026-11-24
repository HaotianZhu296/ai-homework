# HW1-2: Movie Knowledge System with LangChain

Given a list of movie titles, a LangChain `PromptTemplate` builds one prompt per movie and saves them to `prompts.txt`. A second script loads those prompts, sends them to `ChatOpenAI` as a single batch, and prints and saves each movie's genre and plot to `results.json`.

`ChatOpenAI` reads its key, base URL and model from `.env`, so it works with OpenAI or any OpenAI-compatible endpoint. The run shown here used DeepSeek (`deepseek-chat`). To use OpenAI instead, set `OPENAI_API_KEY=sk-...`, remove `OPENAI_BASE_URL`, and set `OPENAI_MODEL=gpt-4o-mini`.

| File | What it does |
|---|---|
| `part1_generate_prompts.py` | Part 1: `PromptTemplate` → 4 prompts → `prompts.txt` |
| `part2_run_llm.py` | Part 2: `prompts.txt` → `ChatOpenAI.batch()` → printed + `results.json` |
| `prompts.txt`, `results.json` | Output of the run below |
| `docs/part1_output.txt`, `docs/part2_output.txt` | Console output of that run |
| `tests/test_movies.py` | Unit tests with a fake chat model (no key needed) |

## Setup and running

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env                       # then put your API key in .env

.venv/bin/python part1_generate_prompts.py
.venv/bin/python part2_run_llm.py
.venv/bin/python -m pytest                 # 6 tests
```

## Part 1: Generate prompts and save to file

```python
movie_prompt = PromptTemplate.from_template(
    'Tell me the genre and the plot of the movie "{title}". '
    'Answer with a JSON object only, using the keys "title", "genre" and "plot", '
    'where "genre" is a list of 1 to 3 standard genre names (for example ["Drama", "Romance"]) '
    'and "plot" is a short summary of 2 to 3 sentences without major spoilers.'
)
```

The template takes one input, `title`, and is filled once for each of "Inception", "Titanic", "The Matrix" and "The Godfather". Some choices behind its wording:

- **JSON with fixed keys.** Part 2 can turn each answer into a record with `title`, `genre` and `plot` instead of storing a paragraph of free text.
- **Genre as a list.** The first version asked only for "the genre". The model then answered in different shapes: `"Romance, Drama, Disaster"`, `"Science fiction / Action (cyberpunk)"`, `"Crime drama"`. Asking for a list of 1 to 3 standard genre names fixed that. All four answers came back in the same shape (`["Crime", "Drama"]`), which a knowledge system can filter or group by.
- **2 to 3 sentences, no major spoilers.** Keeps the plot short and consistent from movie to movie.

`prompts.txt` holds one prompt per line, so Part 2 can read it back line by line. `save_prompts` refuses a prompt that contains a line break, because that prompt would come back split in two.

## Part 2: Load prompts, run the LLM in batch, save results

`load_prompts()` reads `prompts.txt`. Then `llm.batch(prompts, config={"max_concurrency": 4})` sends all four prompts in one call; LangChain runs them in parallel and returns the replies in the same order as the prompts. `JsonOutputParser` reads each reply, and it also accepts JSON wrapped in a code fence. A reply that is not valid JSON is not dropped: it is saved with an `error` field and the raw text, so a bad answer is visible in `results.json` instead of crashing the run.

Console output ([docs/part2_output.txt](docs/part2_output.txt)):

```
Loaded 4 prompts from prompts.txt, sending them as one batch...

Inception  (Science Fiction, Action, Thriller)
  Dom Cobb is a skilled thief who specializes in entering people's dreams to steal secrets from their subconscious. ...

Titanic  (Drama, Romance)
  A young aristocrat, Rose, boards the ill-fated RMS Titanic and feels trapped by her engagement to a wealthy man. ...

The Matrix  (Science Fiction, Action)
  A computer hacker named Neo discovers that the world he knows is an elaborate simulation created by machines to subdue humanity. ...

The Godfather  (Crime, Drama)
  The aging patriarch of an organized crime dynasty in postwar New York decides to transfer control of his clandestine empire to his reluctant youngest son. ...

Saved 4 results to results.json
```

Each entry in [results.json](results.json) keeps the prompt that produced it:

```json
{
  "prompt": "Tell me the genre and the plot of the movie \"The Godfather\". ...",
  "title": "The Godfather",
  "genre": ["Crime", "Drama"],
  "plot": "The aging patriarch of an organized crime dynasty in postwar New York ..."
}
```

## Tests

`tests/test_movies.py` uses LangChain's `FakeListChatModel` in place of `ChatOpenAI`. It checks that:
- the template takes only `title`;
- there is one prompt per movie, and each names the title and asks for genre and plot;
- prompts come back unchanged after the round trip through the file;
- a batch turns plain and code-fenced JSON replies into records;
- a non-JSON reply is kept with an error instead of crashing;
- `results.json` is valid UTF-8 JSON.
