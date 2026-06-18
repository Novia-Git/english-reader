"""
RSS Fetcher Service
-------------------
負責從多個開放授權 RSS 來源抓取文章原文。
支援來源：BBC World、NPR、The Guardian、MIT News、NASA
"""
import re
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape

import feedparser
import httpx

logger = logging.getLogger(__name__)

# ── 設定 ──────────────────────────────────────────────────────────

# 每個來源的設定
RSS_SOURCES: list[dict] = [
    {
        "name": "BBC World",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "min_content_length": 200,
    },
    {
        "name": "NPR News",
        "url": "https://feeds.npr.org/1001/rss.xml",
        "min_content_length": 200,
    },
    {
        "name": "The Guardian",
        "url": "https://www.theguardian.com/world/rss",
        "min_content_length": 200,
    },
    {
        "name": "MIT News",
        "url": "https://news.mit.edu/rss/feed",
        "min_content_length": 150,
    },
    {
        "name": "NASA Breaking News",
        "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
        "min_content_length": 100,
    },
]

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; EnglishReaderBot/1.0; "
        "+https://github.com/your-repo; educational use)"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

HTTP_TIMEOUT = 15  # seconds
MAX_ARTICLES_PER_SOURCE = 5  # 每個來源最多取幾篇


# ── Data Model ────────────────────────────────────────────────────

@dataclass
class RawArticle:
    """RSS 抓下來的原始文章資料（尚未經 AI 改寫）"""
    source_name: str
    source_url: str
    title: str
    raw_content: str           # 清理 HTML 後的純文字
    published_at: datetime
    word_count: int = field(init=False)

    def __post_init__(self):
        self.word_count = len(self.raw_content.split())

    def is_valid(self, min_length: int = 100) -> bool:
        """基本品質 gate：長度夠、有標題"""
        return (
            bool(self.title.strip())
            and len(self.raw_content.strip()) >= min_length
        )


# ── HTML 清理 ─────────────────────────────────────────────────────

# 常見的廣告/導覽文字，清掉避免污染 LLM input
_NOISE_PATTERNS = [
    r"Read more.*?$",
    r"Click here.*?$",
    r"Subscribe.*?$",
    r"Advertisement\s*",
    r"\[.*?\]",              # [image caption], [video] 等
    r"©.*?$",
    r"All rights reserved.*?$",
]
_NOISE_RE = re.compile("|".join(_NOISE_PATTERNS), re.IGNORECASE | re.MULTILINE)


def clean_html(raw: str) -> str:
    """
    移除 HTML tag，清理空白與雜訊文字，回傳純文字。
    feedparser 有時已經清過，但不夠乾淨，這裡做二次清理。
    """
    # 移除 HTML tags
    text = re.sub(r"<[^>]+>", " ", raw)
    # HTML entities（&amp; &nbsp; 等）
    text = unescape(text)
    # 移除雜訊
    text = _NOISE_RE.sub("", text)
    # 合併多餘空白與換行
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_best_content(entry: feedparser.FeedParserDict) -> str:
    """
    feedparser entry 的 content 可能藏在不同欄位，
    依優先順序提取最完整的文字。
    """
    # 1. content（最完整，通常是全文）
    if hasattr(entry, "content") and entry.content:
        return clean_html(entry.content[0].get("value", ""))

    # 2. summary（摘要，次選）
    if hasattr(entry, "summary") and entry.summary:
        return clean_html(entry.summary)

    # 3. description（最後備援）
    if hasattr(entry, "description") and entry.description:
        return clean_html(entry.description)

    return ""


def parse_published_date(entry: feedparser.FeedParserDict) -> datetime:
    """解析發布時間，找不到則用現在時間"""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return datetime.now(tz=timezone.utc)


# ── 核心抓取邏輯 ──────────────────────────────────────────────────

async def fetch_single_source(
    client: httpx.AsyncClient,
    source: dict,
) -> list[RawArticle]:
    """
    抓取單一 RSS 來源，回傳 RawArticle list。
    任何錯誤都 catch 並 log，不讓單一來源失敗影響整體。
    """
    name = source["name"]
    url = source["url"]
    min_length = source.get("min_content_length", 150)
    articles: list[RawArticle] = []

    try:
        response = await client.get(url)
        response.raise_for_status()

        feed = feedparser.parse(response.content)

        if feed.bozo and not feed.entries:
            # bozo=True 表示 XML 有問題，但有 entries 時仍可繼續
            logger.warning(f"[{name}] Feed parse warning: {feed.bozo_exception}")
            return []

        logger.info(f"[{name}] Fetched {len(feed.entries)} entries")

        for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
            content = extract_best_content(entry)
            title = clean_html(entry.get("title", ""))
            link = entry.get("link", url)
            published_at = parse_published_date(entry)

            article = RawArticle(
                source_name=name,
                source_url=link,
                title=title,
                raw_content=content,
                published_at=published_at,
            )

            if article.is_valid(min_length=min_length):
                articles.append(article)
            else:
                logger.debug(
                    f"[{name}] Skipped article (too short or no title): "
                    f"{title[:40]}... len={len(content)}"
                )

        logger.info(f"[{name}] Valid articles: {len(articles)}")

    except httpx.TimeoutException:
        logger.error(f"[{name}] Timeout fetching {url}")
    except httpx.HTTPStatusError as e:
        logger.error(f"[{name}] HTTP {e.response.status_code} for {url}")
    except Exception as e:
        logger.exception(f"[{name}] Unexpected error: {e}")

    return articles


async def fetch_all_sources(
    sources: list[dict] | None = None,
) -> list[RawArticle]:
    """
    並行抓取所有 RSS 來源，回傳全部合格文章。

    Args:
        sources: 自訂來源列表，None 時使用預設 RSS_SOURCES

    Returns:
        list[RawArticle]，已按發布時間降序排列
    """
    sources = sources or RSS_SOURCES

    async with httpx.AsyncClient(
        headers=HTTP_HEADERS,
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
    ) as client:
        # 並行抓取所有來源
        tasks = [fetch_single_source(client, source) for source in sources]
        results = await asyncio.gather(*tasks)

    # 攤平 list of list
    all_articles: list[RawArticle] = []
    for batch in results:
        all_articles.extend(batch)

    # 按發布時間降序（最新的在前）
    all_articles.sort(key=lambda a: a.published_at, reverse=True)

    logger.info(
        f"fetch_all_sources complete: "
        f"{len(all_articles)} articles from {len(sources)} sources"
    )
    return all_articles


def pick_best_article(articles: list[RawArticle]) -> RawArticle | None:
    """
    從候選文章中挑選最適合 B1-B2 學習的一篇。

    挑選策略（優先順序）：
    1. 字數在 300-800 字之間（太短資訊不足，太長改寫成本高）
    2. 標題長度合理（10-100 字元）
    3. 來源可信度（BBC/NPR 優先）
    """
    if not articles:
        return None

    PREFERRED_SOURCES = ["BBC World", "NPR News", "The Guardian"]
    MIN_WORDS, MAX_WORDS = 150, 1000

    # 先篩字數合理的
    candidates = [
        a for a in articles
        if MIN_WORDS <= a.word_count <= MAX_WORDS
        and 10 <= len(a.title) <= 150
    ]

    if not candidates:
        # 放寬條件，至少要有內容
        candidates = [a for a in articles if a.word_count >= 80]

    if not candidates:
        return articles[0] if articles else None

    # 優先返回偏好來源的文章
    for source in PREFERRED_SOURCES:
        preferred = [a for a in candidates if a.source_name == source]
        if preferred:
            return preferred[0]

    return candidates[0]
