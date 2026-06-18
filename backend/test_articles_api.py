"""
T5 Articles API 驗收測試
使用 FastAPI TestClient + mock DB/Redis/LLM
"""
import json
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests._fixture_content import VALID_CONTENT

# ── Mock 工廠 ─────────────────────────────────────────────────────

def make_db_article(
    article_id=1,
    title="Test Article",
    publish_date=None,
    is_published=True,
) -> MagicMock:
    a = MagicMock()
    a.id = article_id
    a.title = title
    a.content = VALID_CONTENT
    a.summary = "Short summary of the article for testing purposes."
    a.difficulty_level = "B1"
    a.highlight_words = json.dumps(["revolutionary", "breakthrough", "efficient", "innovation", "commercial"])
    a.word_count = 306
    a.publish_date = publish_date or date.today()
    a.is_published = is_published
    a.source_name = "BBC World"
    a.source_url = "https://bbc.com/news/test"
    a.source_title = "Original BBC Title"
    a.created_at = datetime.now(tz=timezone.utc)
    return a


def make_app_with_mocks(
    db_article=None,        # GET /today, GET /{id} 回傳的 article
    db_articles=None,       # GET / 列表回傳的 articles
    cache_today=None,       # Redis cache 的值（None = miss）
    cache_article=None,     # Redis article cache
    db_existing=None,       # generate-today 時 DB 裡有沒有既有文章
):
    """建立帶有 mock 依賴的 TestClient"""
    from main import app
    from database import get_db, get_redis

    # Mock DB session
    mock_db = AsyncMock()

    # 設定 scalar_one_or_none 的回傳值
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_article
    mock_result.scalars.return_value.all.return_value = db_articles or []

    # execute 總是回傳 mock_result（簡化版，足夠測試邏輯用）
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    # Mock Redis
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=cache_today)
    mock_redis.setex = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app, raise_server_exceptions=False), mock_db, mock_redis


# ── GET /articles/today ───────────────────────────────────────────

class TestGetTodayArticle:

    def test_returns_article_from_db(self):
        article = make_db_article()
        with patch("api.articles.cache_get", AsyncMock(return_value=None)), \
             patch("api.articles.cache_set", AsyncMock()):
            from main import app
            from database import get_db
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = article
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.commit = AsyncMock()
            mock_db.rollback = AsyncMock()

            async def override():
                yield mock_db

            app.dependency_overrides[get_db] = override
            client = TestClient(app, raise_server_exceptions=True)
            r = client.get("/api/v1/articles/today")
            app.dependency_overrides.clear()

        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Test Article"
        assert data["difficulty_level"] == "B1"
        assert isinstance(data["highlight_words"], list)
        assert len(data["highlight_words"]) == 5

    def test_returns_cached_article_from_redis(self):
        article = make_db_article()
        from api.schemas import ArticleResponse
        cached_json = ArticleResponse.model_validate(article).model_dump_json()

        with patch("api.articles.cache_get", AsyncMock(return_value=cached_json)):
            from main import app
            from database import get_db

            async def override():
                yield AsyncMock()

            app.dependency_overrides[get_db] = override
            client = TestClient(app, raise_server_exceptions=True)
            r = client.get("/api/v1/articles/today")
            app.dependency_overrides.clear()

        assert r.status_code == 200
        assert r.json()["title"] == "Test Article"

    def test_returns_404_when_no_article(self):
        with patch("api.articles.cache_get", AsyncMock(return_value=None)):
            from main import app
            from database import get_db
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.commit = AsyncMock()
            mock_db.rollback = AsyncMock()

            async def override():
                yield mock_db

            app.dependency_overrides[get_db] = override
            client = TestClient(app, raise_server_exceptions=True)
            r = client.get("/api/v1/articles/today")
            app.dependency_overrides.clear()

        assert r.status_code == 404
        assert "hint" in r.json()["detail"]

    def test_response_highlight_words_is_list_not_string(self):
        article = make_db_article()
        with patch("api.articles.cache_get", AsyncMock(return_value=None)), \
             patch("api.articles.cache_set", AsyncMock()):
            from main import app
            from database import get_db
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = article
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.commit = AsyncMock()
            mock_db.rollback = AsyncMock()

            async def override():
                yield mock_db

            app.dependency_overrides[get_db] = override
            client = TestClient(app, raise_server_exceptions=True)
            r = client.get("/api/v1/articles/today")
            app.dependency_overrides.clear()

        assert isinstance(r.json()["highlight_words"], list)


# ── GET /articles/{id} ────────────────────────────────────────────

class TestGetArticleById:

    def test_returns_article_by_id(self):
        article = make_db_article(article_id=42, title="Article 42")
        with patch("api.articles.cache_get", AsyncMock(return_value=None)), \
             patch("api.articles.cache_set", AsyncMock()):
            from main import app
            from database import get_db
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = article
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.commit = AsyncMock()
            mock_db.rollback = AsyncMock()

            async def override():
                yield mock_db

            app.dependency_overrides[get_db] = override
            client = TestClient(app, raise_server_exceptions=True)
            r = client.get("/api/v1/articles/42")
            app.dependency_overrides.clear()

        assert r.status_code == 200
        assert r.json()["id"] == 42

    def test_returns_404_for_missing_article(self):
        with patch("api.articles.cache_get", AsyncMock(return_value=None)):
            from main import app
            from database import get_db
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.commit = AsyncMock()
            mock_db.rollback = AsyncMock()

            async def override():
                yield mock_db

            app.dependency_overrides[get_db] = override
            client = TestClient(app, raise_server_exceptions=True)
            r = client.get("/api/v1/articles/999")
            app.dependency_overrides.clear()

        assert r.status_code == 404


# ── GET /articles（列表）─────────────────────────────────────────

class TestListArticles:

    def test_returns_list(self):
        articles = [make_db_article(article_id=i, title=f"Article {i}") for i in range(1, 4)]
        from main import app
        from database import get_db
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = articles
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        client = TestClient(app, raise_server_exceptions=True)
        r = client.get("/api/v1/articles")
        app.dependency_overrides.clear()

        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_list_items_have_no_full_content(self):
        """列表回應不含 content 全文（節省 bandwidth）"""
        articles = [make_db_article()]
        from main import app
        from database import get_db
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = articles
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        client = TestClient(app, raise_server_exceptions=True)
        r = client.get("/api/v1/articles")
        app.dependency_overrides.clear()

        assert "content" not in r.json()[0]

    def test_pagination_params(self):
        from main import app
        from database import get_db
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        client = TestClient(app, raise_server_exceptions=True)
        r = client.get("/api/v1/articles?page=2&page_size=5")
        app.dependency_overrides.clear()

        assert r.status_code == 200

    def test_invalid_page_returns_422(self):
        from main import app
        client = TestClient(app, raise_server_exceptions=True)
        r = client.get("/api/v1/articles?page=0")   # page 最小為 1
        assert r.status_code == 422


# ── GET /health ───────────────────────────────────────────────────

class TestHealth:

    def test_health_check(self):
        from main import app
        client = TestClient(app, raise_server_exceptions=True)
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ── Schemas ───────────────────────────────────────────────────────

class TestSchemas:

    def test_highlight_words_parsed_from_json_string(self):
        from api.schemas import ArticleResponse
        article = make_db_article()
        response = ArticleResponse.model_validate(article)
        assert isinstance(response.highlight_words, list)
        assert "revolutionary" in response.highlight_words

    def test_highlight_words_empty_on_invalid_json(self):
        from api.schemas import ArticleResponse
        article = make_db_article()
        article.highlight_words = "not valid json"
        response = ArticleResponse.model_validate(article)
        assert response.highlight_words == []

    def test_highlight_words_accepts_list_directly(self):
        from api.schemas import ArticleResponse
        article = make_db_article()
        article.highlight_words = ["a", "b", "c"]
        response = ArticleResponse.model_validate(article)
        assert response.highlight_words == ["a", "b", "c"]


if __name__ == "__main__":
    import traceback

    suites = [
        TestGetTodayArticle,
        TestGetArticleById,
        TestListArticles,
        TestHealth,
        TestSchemas,
    ]

    passed = failed = 0
    for suite in suites:
        instance = suite()
        for name in [m for m in dir(suite) if m.startswith("test_")]:
            method = getattr(instance, name)
            try:
                method()
                print(f"  ✅ {suite.__name__}.{name}")
                passed += 1
            except Exception:
                print(f"  ❌ {suite.__name__}.{name}")
                traceback.print_exc()
                failed += 1

    print(f"\n{'='*60}")
    print(f"結果：{passed} passed / {failed} failed / {passed + failed} total")
