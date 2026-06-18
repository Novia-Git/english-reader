"""
T2 RSS Fetcher 驗收測試
驗收標準：核心邏輯（HTML清理、文章篩選、錯誤處理）100% 通過
網路請求用 mock 模擬，不依賴真實外部連線
"""
import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.rss_fetcher import (
    clean_html,
    extract_best_content,
    parse_published_date,
    fetch_single_source,
    fetch_all_sources,
    pick_best_article,
    RawArticle,
)


# ── clean_html 測試 ───────────────────────────────────────────────

def test_clean_html_removes_tags():
    raw = "<p>Hello <strong>world</strong>!</p>"
    assert clean_html(raw) == "Hello world !"

def test_clean_html_decodes_entities():
    raw = "Scientists &amp; researchers found CO&lt;2&gt; levels rising."
    result = clean_html(raw)
    assert "&amp;" not in result
    assert "Scientists & researchers" in result

def test_clean_html_removes_noise():
    raw = "NASA discovered water on Mars. Read more at nasa.gov. © 2024 All rights reserved."
    result = clean_html(raw)
    assert "Read more" not in result
    assert "All rights reserved" not in result
    assert "NASA discovered water on Mars" in result

def test_clean_html_collapses_whitespace():
    raw = "Hello    \n\n   world   \t  here"
    assert clean_html(raw) == "Hello world here"

def test_clean_html_empty_string():
    assert clean_html("") == ""
    assert clean_html("   ") == ""


# ── RawArticle 測試 ───────────────────────────────────────────────

def make_article(content="word " * 200, title="Test Title") -> RawArticle:
    return RawArticle(
        source_name="Test Source",
        source_url="https://example.com/article",
        title=title,
        raw_content=content,
        published_at=datetime.now(tz=timezone.utc),
    )

def test_raw_article_word_count():
    article = make_article(content="one two three four five")
    assert article.word_count == 5

def test_raw_article_is_valid_passes():
    article = make_article(content="word " * 50)
    assert article.is_valid(min_length=100)

def test_raw_article_is_valid_too_short():
    article = make_article(content="short")
    assert not article.is_valid(min_length=100)

def test_raw_article_is_valid_no_title():
    article = make_article(title="")
    assert not article.is_valid()

def test_raw_article_word_count_auto_calc():
    article = make_article(content="a b c d e")
    assert article.word_count == 5


# ── extract_best_content 測試 ─────────────────────────────────────

def test_extract_best_content_from_content_field():
    entry = MagicMock()
    entry.content = [{"value": "<p>Full article content here.</p>"}]
    result = extract_best_content(entry)
    assert "Full article content here" in result

def test_extract_best_content_fallback_to_summary():
    entry = MagicMock(spec=[])  # spec=[] 讓 hasattr 回傳 False
    entry.summary = "<p>Summary text here.</p>"
    result = extract_best_content(entry)
    assert "Summary text here" in result

def test_extract_best_content_empty():
    entry = MagicMock(spec=[])
    result = extract_best_content(entry)
    assert result == ""


# ── parse_published_date 測試 ─────────────────────────────────────

def test_parse_published_date_valid():
    entry = MagicMock()
    entry.published_parsed = (2024, 6, 15, 10, 30, 0, 0, 0, 0)
    result = parse_published_date(entry)
    assert result.year == 2024
    assert result.month == 6
    assert result.day == 15

def test_parse_published_date_missing_falls_back_to_now():
    entry = MagicMock(spec=[])
    before = datetime.now(tz=timezone.utc)
    result = parse_published_date(entry)
    after = datetime.now(tz=timezone.utc)
    assert before <= result <= after


# ── pick_best_article 測試 ────────────────────────────────────────

def make_full_article(source="NPR News", words=400, title="Valid Title Here") -> RawArticle:
    return RawArticle(
        source_name=source,
        source_url="https://example.com",
        title=title,
        raw_content="word " * words,
        published_at=datetime.now(tz=timezone.utc),
    )

def test_pick_best_article_empty_returns_none():
    assert pick_best_article([]) is None

def test_pick_best_article_prefers_bbc():
    articles = [
        make_full_article(source="MIT News"),
        make_full_article(source="BBC World"),
        make_full_article(source="NPR News"),
    ]
    best = pick_best_article(articles)
    assert best.source_name == "BBC World"

def test_pick_best_article_prefers_npr_over_mit():
    articles = [
        make_full_article(source="MIT News"),
        make_full_article(source="NPR News"),
    ]
    best = pick_best_article(articles)
    assert best.source_name == "NPR News"

def test_pick_best_article_skips_too_short():
    articles = [
        make_full_article(source="BBC World", words=50),   # 太短，被跳過
        make_full_article(source="MIT News", words=400),
    ]
    best = pick_best_article(articles)
    # BBC 太短被排除，應選 MIT
    assert best.source_name == "MIT News"

def test_pick_best_article_skips_too_long():
    articles = [
        make_full_article(source="NPR News", words=1500),  # 太長，被跳過
        make_full_article(source="MIT News", words=400),
    ]
    best = pick_best_article(articles)
    assert best.source_name == "MIT News"

def test_pick_best_article_single_candidate():
    articles = [make_full_article(source="NASA Breaking News", words=300)]
    best = pick_best_article(articles)
    assert best is not None
    assert best.source_name == "NASA Breaking News"


# ── fetch_single_source 整合測試（mock HTTP）────────────────────

BBC_RSS_MOCK = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BBC News</title>
    <item>
      <title>Scientists Discover New Renewable Energy Source</title>
      <link>https://bbc.com/news/science-12345</link>
      <description>
        Researchers at MIT have developed a breakthrough solar panel technology
        that can generate electricity even on cloudy days. The new design uses
        advanced materials to capture a broader spectrum of light, potentially
        doubling the efficiency of existing panels. This could revolutionize
        renewable energy production worldwide and help countries meet their
        carbon reduction targets more quickly than previously thought possible.
      </description>
      <pubDate>Wed, 15 Jun 2024 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Global Climate Summit Reaches Historic Agreement</title>
      <link>https://bbc.com/news/world-67890</link>
      <description>
        World leaders gathered in Geneva have signed a landmark climate agreement
        committing 195 nations to reduce carbon emissions by 50 percent before 2035.
        The deal, described as the most significant climate action in history,
        includes financial support for developing nations transitioning away from
        fossil fuels. Environmental groups cautiously welcomed the agreement while
        calling for stronger enforcement mechanisms to ensure compliance.
      </description>
      <pubDate>Wed, 15 Jun 2024 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


async def _run_fetch_single(mock_content: bytes, status_code: int = 200):
    """Helper：mock HTTP response 並執行 fetch_single_source"""
    mock_response = MagicMock()
    mock_response.content = mock_content
    mock_response.status_code = status_code
    mock_response.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    source = {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "min_content_length": 100}
    return await fetch_single_source(mock_client, source)


def test_fetch_single_source_parses_articles():
    articles = asyncio.run(_run_fetch_single(BBC_RSS_MOCK.encode()))
    assert len(articles) == 2
    assert articles[0].source_name == "BBC World"
    assert "Scientists" in articles[0].title
    assert articles[0].word_count > 50

def test_fetch_single_source_http_error_returns_empty():
    articles = asyncio.run(_run_fetch_single(b"", status_code=403))
    assert articles == []

def test_fetch_single_source_empty_feed_returns_empty():
    empty_feed = b"""<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>"""
    articles = asyncio.run(_run_fetch_single(empty_feed))
    assert articles == []

def test_fetch_single_source_filters_too_short():
    short_feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Short</title>
    <link>https://example.com</link>
    <description>Too short.</description>
    <pubDate>Wed, 15 Jun 2024 10:00:00 GMT</pubDate>
  </item>
</channel></rss>""".encode()
    articles = asyncio.run(_run_fetch_single(short_feed))
    assert articles == []  # 太短被過濾掉


if __name__ == "__main__":
    # 直接執行時的簡易 test runner
    import traceback
    tests = [
        # clean_html
        test_clean_html_removes_tags,
        test_clean_html_decodes_entities,
        test_clean_html_removes_noise,
        test_clean_html_collapses_whitespace,
        test_clean_html_empty_string,
        # RawArticle
        test_raw_article_word_count,
        test_raw_article_is_valid_passes,
        test_raw_article_is_valid_too_short,
        test_raw_article_is_valid_no_title,
        test_raw_article_word_count_auto_calc,
        # extract / parse
        test_extract_best_content_from_content_field,
        test_extract_best_content_fallback_to_summary,
        test_extract_best_content_empty,
        test_parse_published_date_valid,
        test_parse_published_date_missing_falls_back_to_now,
        # pick_best_article
        test_pick_best_article_empty_returns_none,
        test_pick_best_article_prefers_bbc,
        test_pick_best_article_prefers_npr_over_mit,
        test_pick_best_article_skips_too_short,
        test_pick_best_article_skips_too_long,
        test_pick_best_article_single_candidate,
        # fetch_single_source (mock)
        test_fetch_single_source_parses_articles,
        test_fetch_single_source_http_error_returns_empty,
        test_fetch_single_source_empty_feed_returns_empty,
        test_fetch_single_source_filters_too_short,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except Exception:
            print(f"  ❌ {t.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"結果：{passed} passed / {failed} failed / {len(tests)} total")
