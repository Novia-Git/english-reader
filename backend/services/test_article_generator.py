"""
T3 Article Generator 驗收測試
"""
import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests._fixture_content import VALID_CONTENT
from services.rss_fetcher import RawArticle
from services.article_generator import (
    _parse_llm_response, _validate_output,
    _call_openai, _call_anthropic,
    generate_article, GeneratedArticle,
)

def make_raw_article(words=400):
    return RawArticle(
        source_name="BBC World", source_url="https://bbc.com/news/test-123",
        title="Scientists Make Breakthrough in Renewable Energy",
        raw_content="word " * words, published_at=datetime.now(tz=timezone.utc),
    )

VALID_LLM_RESPONSE = {
    "title": "New Solar Technology Could Double Clean Energy Output",
    "content": VALID_CONTENT,
    "summary": "Researchers created panels that work in cloudy weather. New design captures more light. Ready within three years.",
    "difficulty_level": "B1",
    "highlight_words": ["revolutionary", "breakthrough", "efficient", "innovation", "commercial"],
}

# ── _parse_llm_response ──────────────────────────────────────────

def test_parse_clean_json():
    assert _parse_llm_response(json.dumps(VALID_LLM_RESPONSE))["title"] == VALID_LLM_RESPONSE["title"]

def test_parse_json_with_markdown_fence():
    raw = f"```json\n{json.dumps(VALID_LLM_RESPONSE)}\n```"
    assert _parse_llm_response(raw)["difficulty_level"] == "B1"

def test_parse_json_with_plain_fence():
    raw = f"```\n{json.dumps(VALID_LLM_RESPONSE)}\n```"
    assert _parse_llm_response(raw)["highlight_words"] == VALID_LLM_RESPONSE["highlight_words"]

def test_parse_invalid_json_raises():
    with pytest.raises(ValueError, match="invalid JSON"):
        _parse_llm_response("not json")

def test_parse_empty_string_raises():
    with pytest.raises(ValueError):
        _parse_llm_response("")

# ── _validate_output ─────────────────────────────────────────────

def test_validate_passes_valid_data():
    errors = _validate_output(VALID_LLM_RESPONSE)
    assert errors == [], f"Unexpected: {errors}"

def test_validate_b2_level_accepted():
    errors = _validate_output({**VALID_LLM_RESPONSE, "difficulty_level": "B2"})
    assert errors == [], f"Unexpected: {errors}"

def test_validate_missing_title():
    assert any("title" in e for e in _validate_output({**VALID_LLM_RESPONSE, "title": ""}))

def test_validate_missing_content():
    assert any("content" in e for e in _validate_output({**VALID_LLM_RESPONSE, "content": ""}))

def test_validate_content_too_short():
    assert any("short" in e for e in _validate_output({**VALID_LLM_RESPONSE, "content": "Too short."}))

def test_validate_content_too_long():
    long_content = "**word** " + "extra " * 900
    assert any("long" in e for e in _validate_output({**VALID_LLM_RESPONSE, "content": long_content}))

def test_validate_invalid_difficulty_level():
    assert any("difficulty_level" in e for e in _validate_output({**VALID_LLM_RESPONSE, "difficulty_level": "X9"}))

def test_validate_too_few_highlight_words():
    assert any("highlight_words" in e for e in _validate_output({**VALID_LLM_RESPONSE, "highlight_words": ["one"]}))

def test_validate_no_asterisk_markers():
    assert any("highlighted" in e for e in _validate_output({**VALID_LLM_RESPONSE, "content": "normal word " * 350}))

# ── LLM Provider 路由 ────────────────────────────────────────────

def test_call_openai_raises_without_api_key():
    async def run():
        with patch("services.article_generator.settings") as ms:
            ms.openai_api_key = ""
            await _call_openai("prompt")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        asyncio.run(run())

def test_call_anthropic_raises_without_api_key():
    async def run():
        with patch("services.article_generator.settings") as ms:
            ms.anthropic_api_key = ""
            await _call_anthropic("prompt")
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        asyncio.run(run())

def test_call_llm_routes_to_openai():
    async def run():
        with patch("services.article_generator.settings") as ms:
            ms.llm_provider = "openai"; ms.openai_api_key = "sk-test"
            with patch("services.article_generator._call_openai", new_callable=AsyncMock) as m:
                m.return_value = json.dumps(VALID_LLM_RESPONSE)
                from services.article_generator import _call_llm
                await _call_llm("p"); m.assert_called_once_with("p")
    asyncio.run(run())

def test_call_llm_routes_to_anthropic():
    async def run():
        with patch("services.article_generator.settings") as ms:
            ms.llm_provider = "anthropic"; ms.anthropic_api_key = "key"
            with patch("services.article_generator._call_anthropic", new_callable=AsyncMock) as m:
                m.return_value = json.dumps(VALID_LLM_RESPONSE)
                from services.article_generator import _call_llm
                await _call_llm("p"); m.assert_called_once_with("p")
    asyncio.run(run())

def test_call_llm_unknown_provider_raises():
    async def run():
        with patch("services.article_generator.settings") as ms:
            ms.llm_provider = "gemini"
            from services.article_generator import _call_llm
            await _call_llm("p")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        asyncio.run(run())

# ── generate_article 整合測試 ────────────────────────────────────

def run_generate(responses):
    it = iter(responses)
    async def mock_llm(p): return next(it, json.dumps(VALID_LLM_RESPONSE))
    async def run():
        with patch("services.article_generator._call_llm", side_effect=mock_llm):
            return await generate_article(make_raw_article())
    return asyncio.run(run())

def test_generate_success_on_first_attempt():
    a = run_generate([json.dumps(VALID_LLM_RESPONSE)])
    assert isinstance(a, GeneratedArticle)
    assert a.title == VALID_LLM_RESPONSE["title"]
    assert a.difficulty_level == "B1"
    assert len(a.highlight_words) == 5
    assert a.word_count > 0

def test_generate_carries_source_info():
    a = run_generate([json.dumps(VALID_LLM_RESPONSE)])
    assert a.source_name == "BBC World"
    assert a.source_url == "https://bbc.com/news/test-123"
    assert "Scientists" in a.source_title

def test_generate_retries_on_quality_fail():
    call_count = {"n": 0}
    bad = json.dumps({**VALID_LLM_RESPONSE, "content": "Too short."})
    good = json.dumps(VALID_LLM_RESPONSE)
    async def mock_llm(p):
        r = bad if call_count["n"] == 0 else good
        call_count["n"] += 1; return r
    async def run():
        with patch("services.article_generator._call_llm", side_effect=mock_llm):
            return await generate_article(make_raw_article())
    a = asyncio.run(run())
    assert a is not None
    assert call_count["n"] == 2

def test_generate_raises_after_max_retries():
    bad = json.dumps({**VALID_LLM_RESPONSE, "content": "Too short."})
    async def run():
        with patch("services.article_generator._call_llm", return_value=bad):
            await generate_article(make_raw_article())
    with pytest.raises(RuntimeError, match="failed after"):
        asyncio.run(run())

def test_generate_handles_json_fence():
    fenced = f"```json\n{json.dumps(VALID_LLM_RESPONSE)}\n```"
    a = run_generate([fenced])
    assert a.title == VALID_LLM_RESPONSE["title"]

def test_generate_highlight_words_capped_at_5():
    data = {**VALID_LLM_RESPONSE, "highlight_words": ["a","b","c","d","e","f","g"]}
    assert len(run_generate([json.dumps(data)]).highlight_words) == 5


if __name__ == "__main__":
    import traceback
    tests = [
        test_parse_clean_json, test_parse_json_with_markdown_fence,
        test_parse_json_with_plain_fence, test_parse_invalid_json_raises,
        test_parse_empty_string_raises, test_validate_passes_valid_data,
        test_validate_b2_level_accepted, test_validate_missing_title,
        test_validate_missing_content, test_validate_content_too_short,
        test_validate_content_too_long, test_validate_invalid_difficulty_level,
        test_validate_too_few_highlight_words, test_validate_no_asterisk_markers,
        test_call_openai_raises_without_api_key, test_call_anthropic_raises_without_api_key,
        test_call_llm_routes_to_openai, test_call_llm_routes_to_anthropic,
        test_call_llm_unknown_provider_raises, test_generate_success_on_first_attempt,
        test_generate_carries_source_info, test_generate_retries_on_quality_fail,
        test_generate_raises_after_max_retries, test_generate_handles_json_fence,
        test_generate_highlight_words_capped_at_5,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t(); print(f"  ✅ {t.__name__}"); passed += 1
        except Exception:
            print(f"  ❌ {t.__name__}"); traceback.print_exc(); failed += 1
    print(f"\n{'='*55}")
    print(f"結果：{passed} passed / {failed} failed / {len(tests)} total")
