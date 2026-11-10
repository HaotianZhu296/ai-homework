# Prompt Engineering (Homework 0-6)

Two prompts, each tested by running it against a real model and checking the output with code:

| Part | Prompt | What it does | Result |
| --- | --- | --- | --- |
| 1 | [`part1_weather/prompt.md`](part1_weather/prompt.md) | Turns a location into the current NOAA forecast, as strict JSON | **8/8** test inputs pass: valid JSON, exactly the 7 fields, values identical to an independent Python implementation |
| 2 | [`part2_sentiment/prompt.md`](part2_sentiment/prompt.md) | Classifies a sentence as positive, negative, neutral or sarcastic | **95%** of sentences and **89.7%** of the 1,000 records match the human majority label |

All runs used `claude-sonnet-5-5` unless noted. The prompt under test is the model's **only** system prompt (see [How the prompts are run](#how-the-prompts-are-run)).

---

## Part 1: NOAA weather forecast as JSON

### The prompt

[`part1_weather/prompt.md`](part1_weather/prompt.md) is organised as Role → Tool → Input → Procedure → Output rules → Examples. Its design choices:

- **Input:** coordinates, a US place name, a street address or a ZIP code, plus an optional period (`Chicago, IL | Wednesday`).
- **Intermediate calls, spelled out step by step:**
  1. Geocode the input if it is not coordinates (OpenStreetMap Nominatim, US only).
  2. Call `GET /points/{lat},{lon}`, rounding to 4 decimals because NOAA redirects more precise coordinates.
  3. Read the `forecast` URL from that response. The prompt forbids building a gridpoints URL by hand.
  4. Call that URL and pick one period.
- **Extraction:** a mapping table from each output key to its NOAA field. Values are copied verbatim ("do not convert units, round, translate, reword or summarize").
- **Strict output:** one JSON object with exactly the 7 keys, in a fixed order, with `temperature` as a number and nothing outside the braces.
- **Failures are part of the contract.** When there is no forecast (outside the US, unknown place, unknown period, NOAA error), the reply has the same 7 keys: `location` echoes the input and every other value is `null`. The caller always gets the same shape.
- **No hallucinated values:** "every value you report must come from a tool response".

Output fields: `location`, `forecast_period`, `temperature`, `temperature_unit`, `short_forecast`, `wind_speed`, `wind_direction`. The assignment writes the last one as "wind direction". It is spelled `wind_direction` here to match the snake_case of the other six keys.

### Results

The assistant ran each input with only an `http_get` tool. [`reference.py`](part1_weather/reference.py) then ran the same procedure in plain Python. A run passes when the reply is valid by the output rules and every field equals the reference. Full log: [`results/weather_runs.json`](part1_weather/results/weather_runs.json).

| Input | Reply | Calls | Pass |
| --- | --- | --- | --- |
| `47.6062,-122.3321` (assignment example) | `{"location": "Seattle, WA", "forecast_period": "Tonight", "temperature": 49, "temperature_unit": "F", "short_forecast": "Mostly Cloudy then Chance Light Rain", "wind_speed": "6 to 14 mph", "wind_direction": "S"}` | 2 | ✅ |
| `Boston, MA` | `{"location": "Boston, MA", "forecast_period": "Tonight", "temperature": 44, "temperature_unit": "F", "short_forecast": "Mostly Cloudy", "wind_speed": "10 to 15 mph", "wind_direction": "W"}` | 3 | ✅ |
| `Denver` | `{"location": "Denver, CO", "forecast_period": "Tonight", "temperature": 40, ..., "wind_speed": "3 mph", "wind_direction": "SW"}` | 3 | ✅ |
| `1600 Pennsylvania Ave NW, Washington, DC` | `{"location": "Washington, DC", "forecast_period": "Overnight", "temperature": 40, ..., "short_forecast": "Partly Cloudy"}` | 3 | ✅ |
| `Chicago, IL \| tuesday night` | `{"location": "Chicago, IL", "forecast_period": "Tuesday Night", "temperature": 44, ..., "wind_direction": "WSW"}` | 3 | ✅ |
| `Chicago, IL \| Wednesday` | `{"location": "Chicago, IL", "forecast_period": "Veterans Day", "temperature": 54, "temperature_unit": "F", "short_forecast": "Chance Rain", ...}` | 3 | ✅ |
| `Paris, France` | `{"location": "Paris, France", "forecast_period": null, ... null}` | 1 | ✅ |
| `Chicago, IL \| Someday` | `{"location": "Chicago, IL \| Someday", "forecast_period": null, ... null}` | 3 | ✅ |

Run on 2026-11-10 (UTC). Forecasts change, so a rerun gives different values but should give the same pass/fail.

### What testing changed in the prompt

The final prompt came out of two problems found by running it:

1. **Holiday period names.** Asking for `Chicago, IL | Wednesday` first returned the error output. NOAA had named that period **"Veterans Day"** (11 November 2026 is a Wednesday), so no period matched by name. The prompt now falls back to the weekday of `startTime` plus `isDaytime`, and reports NOAA's real name.
2. **Explanations around the JSON.** Once that fallback existed, the model explained it before the JSON ("No period is named 'Wednesday', so I used the date fallback…"). The reply was then no longer parseable, and the validator caught it. Two rules fixed it: "the first character of your reply is `{` and the last is `}`", and "never explain your steps, not even when you used a fallback". Three reruns of the holiday case then passed.

---

## Part 2: Sentiment classification

### The prompt

[`part2_sentiment/prompt.md`](part2_sentiment/prompt.md) follows the prompt template sections:

| Section | Content |
| --- | --- |
| **Role** | An expert annotator of short customer comments |
| **Task** | Exactly one of `positive`, `negative`, `neutral`, `sarcastic` |
| **Context** | A definition of each label, with an example |
| **Instructions** | Decision rules for the hard boundaries:<br>• sarcasm needs a cue (mock praise of a bad situation, "… not", "oh sure", "yeah, because", praise followed by a jab); exaggerated praise with no cue stays `positive`<br>• sarcasm beats `negative`<br>• a plain bad outcome is `negative`<br>• lukewarm or mixed is `neutral` |
| **Output format** | `{"rationale": "...", "label": "..."}`, with the rationale first so the label follows from it |
| **Examples** | Five few-shot examples, all written for this prompt. None comes from the dataset, so the score is not inflated |

### Data

The assignment points to `hw0-3_multi_annotator_dataset_list.csv`. That file was never available, so this uses the same stand-in as Homework 0-3: [`part2_sentiment/data/sample_multi_annotator_dataset.csv`](part2_sentiment/data/sample_multi_annotator_dataset.csv). It has 1,000 records with 3 annotator labels each, over 20 distinct sentences. To use the official file, save it as `part2_sentiment/data/hw0-3_multi_annotator_dataset_list.csv` and the script picks it up automatically.

### Results

Each distinct sentence is classified once and scored three ways ([`metrics.py`](part2_sentiment/metrics.py)):

| Metric | `claude-sonnet-5-5` | `claude-haiku-5-5` |
| --- | --- | --- |
| Sentence accuracy (20 sentences, gold = majority of all their votes) | **95.0%** | 90.0% |
| Record accuracy (1,000 records, gold = majority of the record's 3 votes) | **89.7%** | 84.2% |
| Macro-F1 (record level) | **0.899** | 0.831 |
| Agreement with a single annotator's vote | **81.8%** | 76.5% |
| Agreement of two annotators with each other | 73.2% | 73.2% |
| Invalid replies | 0 | 0 |

- **Agreement with annotators:** the model agrees with an individual annotator more often (81.8%) than two annotators agree with each other (73.2%). Its labels are about as reliable as a human annotator's.
- **Record accuracy is lower than sentence accuracy** because the same sentence gets different majority labels on different records. No single answer can match every record.

Per-label results for Sonnet (record level):

| Label | Precision | Recall | F1 |
| --- | --- | --- | --- |
| positive | 0.790 | 0.947 | 0.861 |
| negative | 0.959 | 0.922 | 0.940 |
| neutral | 0.919 | 0.948 | 0.933 |
| sarcastic | 0.938 | 0.796 | 0.861 |

**Error analysis.** Sonnet's only miss is *"Wow, that's just unbelievable!"*, labelled `positive`. The annotators split on it as well: 94 sarcastic, 50 positive and 45 negative votes. Its rationale was "exaggerated exclamation with no clear cue of mock praise". That is the "no cue → not sarcastic" rule working as written, on a sentence that is ambiguous without context. This one sentence causes most of the sarcastic → positive confusions (52 records). Haiku also misses it (as `neutral`), and calls *"It works as expected."* `positive` where annotators said `neutral`. The prompt was **not** tuned on these sentences, so the scores are an honest measure rather than a fit to the data.

Full predictions and rationales: [`results/sentiment_claude-sonnet-5-5.json`](part2_sentiment/results/sentiment_claude-sonnet-5-5.json), [`results/sentiment_claude-haiku-5-5.json`](part2_sentiment/results/sentiment_claude-haiku-5-5.json).

---

## How the prompts are run

[`llm.py`](llm.py) calls Claude through the Claude Code CLI in headless mode (`claude -p`):

- `--system-prompt` **replaces** the CLI's own system prompt, so the prompt under test is the only system prompt the model sees.
- `--tools ""` removes every built-in tool, and `--setting-sources ""` ignores local settings.
- Each call runs in an empty temporary directory.

For Part 1, the model gets exactly one tool through MCP: `http_get`, from [`http_tool_server.py`](part1_weather/http_tool_server.py). It only allows `https://api.weather.gov` and `https://nominatim.openstreetmap.org`, sends a descriptive User-Agent as NOAA requires, and rate-limits Nominatim to 1 request/second.

```
part1_weather/
  prompt.md             the weather prompt
  http_tool_server.py   MCP server exposing the http_get tool
  reference.py          the same procedure in plain Python, plus the output validator
  run_weather.py        runs the prompt on test inputs and compares with reference.py
  results/              run logs
part2_sentiment/
  prompt.md             the classification prompt
  run_sentiment.py      classifies every distinct sentence, then scores
  metrics.py            dataset loading, reply parsing, metrics
  data/  results/
llm.py                  headless Claude CLI wrapper
tests/                  unit tests (validator, period matching, tool allow-list, metrics)
```

## Running it

Requires Python 3.12 and the [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) (logged in).

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python part1_weather/run_weather.py                      # 8 default inputs
python part1_weather/run_weather.py "Austin, TX | Tonight"
python part2_sentiment/run_sentiment.py                  # Sonnet
python part2_sentiment/run_sentiment.py --model claude-haiku-5-5
pytest                                                   # 15 unit tests, no network or model calls
```
