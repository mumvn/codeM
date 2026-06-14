from pydantic import BaseModel, Field


class Article(BaseModel):
    id: int
    title: str
    link: str
    pub_date: str
    category: str
    raw_description: str
    ai_summary: str | None


class SyncFeedResult(BaseModel):
    feed: str
    category: str
    added: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class SyncResponse(BaseModel):
    added: int
    skipped: int
    feeds: list[SyncFeedResult]
