# Microsoft AI Architecture Digest

A secure FastAPI and SQLite dashboard that aggregates five curated Microsoft AI RSS feeds across the Platform, Orchestration, and End-User layers. New feed entries are cleaned, summarized by Google Gemini into exactly five architecture-focused lines, and cached locally.

## Architecture

- **Backend:** FastAPI with a shared asynchronous HTTP client and security headers.
- **Persistence:** SQLite in WAL mode with a unique article-link constraint.
- **Feed pipeline:** `feedparser` plus Beautiful Soup HTML sanitization.
- **LLM:** Google Gemini `gemini-2.5-flash`; the API key remains server-side.
- **Frontend:** Responsive HTML, CSS, and vanilla JavaScript dashboard.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set LLM_API_KEY
python app.py
```

Open <http://127.0.0.1:8000>. API documentation is available at <http://127.0.0.1:8000/docs>.

## API

- `GET /api/articles` returns cached articles, newest first. Optional query parameters: `category` and `limit`.
- `POST /api/sync` fetches all configured feeds, skips existing links, generates summaries for new entries, and returns per-feed results.
- `GET /health` provides a lightweight health response.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_API_KEY` | none | Required Google Gemini API key. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model used for summaries. |
| `DATABASE_PATH` | `architecture_digest.db` | SQLite database location. |
| `REQUEST_TIMEOUT_SECONDS` | `30` | Feed and Gemini request timeout. |
| `MAX_ARTICLE_CHARS` | `20000` | Maximum description characters sent to Gemini. |

Secrets in `.env` and local database files are excluded from version control.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```
