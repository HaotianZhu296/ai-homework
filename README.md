# AI Homework

Course assignments. Each assignment lives on its own branch:

| Branch | Assignment | Stack |
| --- | --- | --- |
| [`hw0-1`](../../tree/hw0-1) | **Tic Tac Toe**: online Player vs Player (WebSocket rooms, quick match, chat, reconnect) and Player vs Computer (minimax AI) | Node.js, `ws`, vanilla JS |
| [`hw0-2`](../../tree/hw0-2) | **Mood Recipes**: user accounts (bcrypt, password reset), favorite recipes per user, custom moods | FastAPI, SQLAlchemy + SQLite, Tailwind |
| [`hw0-3`](../../tree/hw0-3) | **Multi-Annotator Sentiment**: annotate sentences with 3 annotators, immutable storage, agreement stats, rerunnable classifier | FastAPI, SQLite, scikit-learn |
| [`hw0-4`](../../tree/hw0-4) | **Movie Keyword Search**: OpenSearch `match` search over 1,250 movies behind API Gateway + Lambda, provisioned in one CDK stack, with a React results page | AWS CDK (Python), OpenSearch, Lambda, API Gateway, React |

```bash
git clone -b hw0-2 https://github.com/HaotianZhu296/ai-homework.git hw0-2
```

Each branch has its own README with setup steps, features and tests.
