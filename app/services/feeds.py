import asyncio
import calendar
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.config import Settings
from app.database import db_session
from app.models import SyncFeedResult, SyncResponse
from app.services.llm import SummaryGenerationError, generate_summary


@dataclass(frozen=True)
class FeedSource:
    category: str
    url: str


FEEDS = (
    FeedSource("platform", "https://devblogs.microsoft.com/foundry/feed/"),
    FeedSource("platform", "https://techcommunity.microsoft.com/category/azure-ai-foundry/blog/azure-ai-foundry-blog/rss"),
    FeedSource("orchestration", "https://www.microsoft.com/en-us/microsoft-copilot/blog/copilot-studio/feed/"),
    FeedSource("orchestration", "https://techcommunity.microsoft.com/category/microsoft365copilot/blog/copilot-studio-blog/rss"),
    FeedSource("end-user", "https://techcommunity.microsoft.com/category/microsoft365copilot/blog/microsoft365copilotblog/rss"),
)

_sync_lock = asyncio.Lock()


def clean_html(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def normalize_date(entry: dict) -> str:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def valid_article_link(link: str) -> bool:
    parsed = urlparse(link)
    return parsed.scheme == "https" and bool(parsed.netloc)


def article_exists(link: str, settings: Settings) -> bool:
    with db_session(settings.database_path) as connection:
        return connection.execute("SELECT 1 FROM articles WHERE link = ?", (link,)).fetchone() is not None


def insert_article(article: tuple[str, str, str, str, str, str], settings: Settings) -> bool:
    with db_session(settings.database_path) as connection:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO articles
               (title, link, pub_date, category, raw_description, ai_summary)
               VALUES (?, ?, ?, ?, ?, ?)""",
            article,
        )
        return cursor.rowcount == 1


async def sync_feeds(settings: Settings, client: httpx.AsyncClient) -> SyncResponse:
    results: list[SyncFeedResult] = []
    async with _sync_lock:
        for source in FEEDS:
            result = SyncFeedResult(feed=source.url, category=source.category)
            results.append(result)
            try:
                response = await client.get(
                    source.url,
                    headers={"User-Agent": "Microsoft-AI-Architecture-Digest/1.0"},
                    timeout=settings.request_timeout_seconds,
                    follow_redirects=True,
                )
                response.raise_for_status()
                parsed = feedparser.parse(response.content)
                if parsed.bozo and not parsed.entries:
                    raise ValueError("Feed XML could not be parsed")
            except (httpx.HTTPError, ValueError) as exc:
                result.errors.append(f"Feed fetch failed: {type(exc).__name__}")
                continue

            for entry in parsed.entries:
                link = str(entry.get("link", "")).strip()
                if not valid_article_link(link):
                    result.errors.append("Skipped an entry with an invalid HTTPS link")
                    continue
                if article_exists(link, settings):
                    result.skipped += 1
                    continue

                title = clean_html(str(entry.get("title", "Untitled article")))
                description = clean_html(str(entry.get("summary") or entry.get("description") or ""))
                if not description:
                    result.errors.append(f"No description available for {link}")
                    continue
                try:
                    summary = await generate_summary(description, settings, client)
                    inserted = insert_article(
                        (title, link, normalize_date(entry), source.category, description, summary),
                        settings,
                    )
                    if inserted:
                        result.added += 1
                    else:
                        result.skipped += 1
                except SummaryGenerationError as exc:
                    result.errors.append(f"Summary failed for {link}: {exc}")

    return SyncResponse(
        added=sum(item.added for item in results),
        skipped=sum(item.skipped for item in results),
        feeds=results,
    )
