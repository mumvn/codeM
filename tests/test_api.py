from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.database import db_session
from app.main import app


def test_articles_endpoint_and_missing_key_sync(tmp_path: Path):
    settings = Settings(database_path=tmp_path / "api.db", llm_api_key=None)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            with db_session(settings.database_path) as connection:
                connection.execute(
                    """INSERT INTO articles
                    (title, link, pub_date, category, raw_description, ai_summary)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    ("Test", "https://example.com/test", "2026-01-01T00:00:00+00:00", "platform", "Raw", "• 1\n• 2\n• 3\n• 4\n• 5"),
                )
            response = client.get("/api/articles")
            assert response.status_code == 200
            assert response.json()[0]["title"] == "Test"
            assert "LLM_API_KEY" not in response.text

            sync_response = client.post("/api/sync")
            assert sync_response.status_code == 503
    finally:
        app.dependency_overrides.clear()
