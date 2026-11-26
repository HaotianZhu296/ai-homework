# AI Homework

Course assignments. Each assignment lives on its own branch:

| Branch | Assignment | Stack |
| --- | --- | --- |
| [`hw0-1`](../../tree/hw0-1) | **Tic Tac Toe**: online Player vs Player (WebSocket rooms, quick match, chat, reconnect) and Player vs Computer (minimax AI) | Node.js, `ws`, vanilla JS |
| [`hw0-2`](../../tree/hw0-2) | **Mood Recipes**: user accounts (bcrypt, password reset), favorite recipes per user, custom moods | FastAPI, SQLAlchemy + SQLite, Tailwind |
| [`hw0-3`](../../tree/hw0-3) | **Multi-Annotator Sentiment**: annotate sentences with 3 annotators, immutable storage, agreement stats, rerunnable classifier | FastAPI, SQLite, scikit-learn |
| [`hw0-4`](../../tree/hw0-4) | **Movie Keyword Search**: OpenSearch `match` search over 1,250 movies behind API Gateway + Lambda, provisioned in one CDK stack, with a React results page | AWS CDK (Python), OpenSearch, Lambda, API Gateway, React |
| [`hw0-6`](../../tree/hw0-6) | **Prompt Engineering**: a NOAA weather prompt that returns strict JSON (tool-using, checked against a Python reference), and a 4-way sentiment prompt scored against multi-annotator labels | Claude (headless CLI), MCP tool server, Python |
| [`hw0-7`](../../tree/hw0-7) | **LLM-as-a-Judge Code Grading**: label reference solutions in Label Studio, build an eval JSONL, grade model code on a 1–5 rubric with repeated judge runs (mean, variance, bootstrap CI), cross-checked with unit tests | Label Studio, Claude, Python |
| [`hw0-9`](../../tree/hw0-9) | **SmartHire AI Resume Screening**: Google Form intake, Zapier workflow, job requirements in DynamoDB, LLM judge with code-computed weighted score and mandatory-requirement rule, candidate ranking, advance/reject emails | Zapier, Google Forms, AWS CDK (Python), DynamoDB, Lambda, API Gateway |
| [`hw1-1`](../../tree/hw1-1) | **Programming Tutor Chatbot**: one-shot API call, multi-turn CLI chatbot, system prompt that cites sources with Q&A logged to `chat_log.txt`, Streamlit web chat | OpenAI Python SDK (DeepSeek endpoint), Streamlit, pytest |
| [`hw1-2`](../../tree/hw1-2) | **Movie Knowledge System**: LangChain `PromptTemplate` builds one prompt per movie into `prompts.txt`, `ChatOpenAI` runs them as one batch, genre and plot parsed into `results.json` | LangChain (`langchain-openai`, DeepSeek endpoint), pytest |
| [`hw1-3`](../../tree/hw1-3) | **LLM Tools**: number-to-words and square functions as LangChain tools, a prompt that lets the model pick the right tool in one `llm.invoke()` per query, and a persistent SQLite LLM cache | LangChain (`langchain-openai`, DeepSeek endpoint), SQLite, pytest |

```bash
git clone -b hw0-2 https://github.com/HaotianZhu296/ai-homework.git hw0-2
```

Each branch has its own README with setup steps, features and tests.
