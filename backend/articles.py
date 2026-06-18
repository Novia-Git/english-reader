"""
Articles API
------------
GET  /api/v1/articles/today          - 取得今日文章（Redis cache → SQLite fallback）
POST /api/v1/articles/generate-today - 手動觸發今日文章生成（開發測試用）
GET  /api/v1/articles/{article_id}   - 取得指定文章
GET  /api/v1/articles                - 取得文章列表（分頁）
"""
import json
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, cache_get, cache_set, CACHE_KEY_TODAY_ARTICLE, CACHE_KEY_ARTICLE
from models import Article
from api.schemas import ArticleResponse, ArticleListItem, GenerateTodayResponse
from services.rss_fetcher import fetch_all_sources, pick_best_article
from services.article_generator import generate_article

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/articles", tags=["articles"])


# ── Helpers ───────────────────────────────────────────────────────

def _article_cache_key(article_id: int) -> str:
    return CACHE_KEY_ARTICLE.format(article_id=article_id)


async def _get_article_by_id(article_id: int, db: AsyncSession) -> Article:
    """從 DB 取得文章，不存在則拋 404"""
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found")
    return article


async def _article_to_response(article: Article) -> ArticleResponse:
    return ArticleResponse.model_validate(article)


# ── Routes ────────────────────────────────────────────────────────

@router.get("/today", response_model=ArticleResponse, summary="取得今日文章")
async def get_today_article(db: AsyncSession = Depends(get_db)):
    """
    取得今日（台灣時間）的學習文章。
    優先從 Redis cache 讀取，miss 時查 SQLite，都沒有則回傳 404。
    """
    today = date.today()

    # 1. 查 Redis cache
    cached = await cache_get(CACHE_KEY_TODAY_ARTICLE)
    if cached:
        logger.info("Today's article served from Redis cache")
        data = json.loads(cached)
        return ArticleResponse(**data)

    # 2. 查 SQLite
    result = await db.execute(
        select(Article)
        .where(Article.publish_date == today, Article.is_published == True)
        .order_by(desc(Article.created_at))
        .limit(1)
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "No article available for today yet.",
                "hint": "POST /api/v1/articles/generate-today to generate one.",
                "date": str(today),
            },
        )

    # 3. 存入 cache 供下次使用
    response = await _article_to_response(article)
    await cache_set(CACHE_KEY_TODAY_ARTICLE, response.model_dump_json())
    logger.info(f"Today's article (id={article.id}) cached in Redis")

    return response


@router.post(
    "/generate-today",
    response_model=GenerateTodayResponse,
    summary="手動觸發今日文章生成",
    description="開發 / 測試用。正式環境由 APScheduler 每日自動觸發。",
)
async def generate_today_article(db: AsyncSession = Depends(get_db)):
    """
    手動執行完整的文章生成 pipeline：
    RSS fetch → pick best → LLM rewrite → save to DB → cache to Redis
    """
    today = date.today()

    # 防止重複生成
    existing = await db.execute(
        select(Article).where(
            Article.publish_date == today,
            Article.is_published == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Today's article already exists.",
                "hint": "GET /api/v1/articles/today to read it.",
            },
        )

    # Pipeline: RSS → pick → LLM → DB → cache
    logger.info("Starting article generation pipeline...")

    # Step 1: RSS fetch
    raw_articles = await fetch_all_sources()
    if not raw_articles:
        raise HTTPException(
            status_code=503,
            detail="Failed to fetch articles from RSS sources. Please try again later.",
        )
    logger.info(f"Fetched {len(raw_articles)} raw articles")

    # Step 2: Pick best
    best = pick_best_article(raw_articles)
    if not best:
        raise HTTPException(status_code=503, detail="No suitable article found from RSS sources.")
    logger.info(f"Selected: '{best.title[:60]}' from {best.source_name}")

    # Step 3: LLM rewrite
    generated = await generate_article(best)
    logger.info(f"LLM generated: '{generated.title}' ({generated.word_count} words)")

    # Step 4: Save to DB
    article = Article(
        source_title=generated.source_title,
        source_url=generated.source_url,
        source_name=generated.source_name,
        title=generated.title,
        content=generated.content,
        summary=generated.summary,
        difficulty_level=generated.difficulty_level,
        word_count=generated.word_count,
        highlight_words=json.dumps(generated.highlight_words),
        publish_date=today,
        is_published=True,
    )
    db.add(article)
    await db.flush()   # 取得 article.id，但還未 commit
    article_id = article.id
    logger.info(f"Article saved to DB: id={article_id}")

    # Step 5: Cache to Redis
    response_data = ArticleResponse.model_validate(article)
    await cache_set(CACHE_KEY_TODAY_ARTICLE, response_data.model_dump_json())
    logger.info("Article cached in Redis")

    return GenerateTodayResponse(
        message="Today's article generated successfully.",
        article_id=article_id,
        title=generated.title,
        word_count=generated.word_count,
        difficulty_level=generated.difficulty_level,
        highlight_words=generated.highlight_words,
    )


@router.get("/{article_id}", response_model=ArticleResponse, summary="取得指定文章")
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """
    以 article_id 取得單篇文章。
    先查 Redis，miss 時查 DB 並回寫 cache。
    """
    cache_key = _article_cache_key(article_id)

    # 查 Redis
    cached = await cache_get(cache_key)
    if cached:
        return ArticleResponse(**json.loads(cached))

    # 查 DB
    article = await _get_article_by_id(article_id, db)
    response = await _article_to_response(article)

    # 回寫 cache（TTL 7 天，舊文章也值得 cache）
    await cache_set(cache_key, response.model_dump_json(), ttl=604800)

    return response


@router.get("", response_model=list[ArticleListItem], summary="取得文章列表")
async def list_articles(
    page: int = Query(1, ge=1, description="頁碼，從 1 開始"),
    page_size: int = Query(10, ge=1, le=50, description="每頁筆數"),
    db: AsyncSession = Depends(get_db),
):
    """
    取得已發佈文章列表，按發佈日期降序。
    回傳精簡資訊（不含全文），適合用於首頁列表。
    """
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Article)
        .where(Article.is_published == True)
        .order_by(desc(Article.publish_date))
        .offset(offset)
        .limit(page_size)
    )
    articles = result.scalars().all()
    return [ArticleListItem.model_validate(a) for a in articles]
