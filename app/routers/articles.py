import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.config import Settings, get_settings
from app.database import db_session
from app.models import Article, SyncResponse
from app.services.feeds import sync_feeds

router = APIRouter(prefix="/api", tags=["articles"])


@router.get("/articles", response_model=list[Article])
def list_articles(
    category: str | None = Query(default=None, pattern="^(platform|orchestration|end-user)$"),
    limit: int = Query(default=100, ge=1, le=500),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    query = "SELECT * FROM articles"
    params: list[object] = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY pub_date DESC, id DESC LIMIT ?"
    params.append(limit)
    with db_session(settings.database_path) as connection:
        return [dict(row) for row in connection.execute(query, params).fetchall()]


@router.post("/sync", response_model=SyncResponse)
async def synchronize(request: Request, settings: Settings = Depends(get_settings)) -> SyncResponse:
    if not settings.llm_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM_API_KEY is not configured on the server.",
        )
    client: httpx.AsyncClient = request.app.state.http_client
    return await sync_feeds(settings, client)
