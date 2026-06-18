from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from redis.asyncio import Redis
from typing import AsyncGenerator
from config import get_settings

settings = get_settings()

# ── SQLite async engine ────────────────────────────────────────────
# SQLite 特殊設定：check_same_thread=False 讓 async 可以跨 thread 使用
engine = create_async_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.debug,  # debug 模式會印出所有 SQL
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # commit 後物件仍可讀取，避免 lazy load 問題
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency：取得 DB session，request 結束自動關閉"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Redis ──────────────────────────────────────────────────────────
_redis_client: Redis | None = None


def get_redis() -> Redis:
    """取得 Redis client（singleton）"""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,  # 自動 decode bytes → str
        )
    return _redis_client


# ── Cache Helpers ──────────────────────────────────────────────────
CACHE_KEY_TODAY_ARTICLE = "article:today"
CACHE_KEY_ARTICLE = "article:{article_id}"


async def cache_set(key: str, value: str, ttl: int | None = None) -> None:
    redis = get_redis()
    ttl = ttl or settings.cache_ttl_seconds
    await redis.setex(key, ttl, value)


async def cache_get(key: str) -> str | None:
    redis = get_redis()
    return await redis.get(key)


async def cache_delete(key: str) -> None:
    redis = get_redis()
    await redis.delete(key)
