"""
Article Generator Service
--------------------------
將 RSS 原始文章透過 LLM 改寫為 B1-B2 難度的英文學習文章。
同時支援 OpenAI 與 Anthropic，由 config.llm_provider 控制。
"""
import json
import logging
import re
from dataclasses import dataclass

import httpx

from config import get_settings
from services.rss_fetcher import RawArticle

logger = logging.getLogger(__name__)
settings = get_settings()

# ── 常數 ──────────────────────────────────────────────────────────

TARGET_WORD_COUNT_MIN = 300
TARGET_WORD_COUNT_MAX = 500
HIGHLIGHT_WORD_COUNT = 5       # 每篇標記幾個學習重點單字
LLM_MAX_TOKENS = 1200
LLM_TEMPERATURE = 0.7
MAX_RETRIES = 2                # 品質不合格時最多重試幾次


# ── Output Schema ─────────────────────────────────────────────────

@dataclass
class GeneratedArticle:
    """LLM 改寫後的結構化文章"""
    title: str
    content: str
    summary: str               # 2-3 句摘要
    difficulty_level: str      # B1 or B2
    highlight_words: list[str] # 5 個學習重點單字
    word_count: int

    # 原始來源資訊（從 RawArticle 帶過來）
    source_name: str
    source_url: str
    source_title: str


# ── Prompt ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert English teacher who rewrites news articles for language learners.
Your task is to rewrite the given article for B1-B2 level learners (intermediate, \
university students or working adults).

REWRITING RULES:
1. Target length: 300-500 words
2. Use clear, simple sentence structures (avoid overly complex subordinate clauses)
3. Replace difficult vocabulary with more common alternatives, but keep 5 key \
   advanced words that are worth learning — mark them in the text with double \
   asterisks like **word**
4. Keep all the important facts from the original
5. Write in a neutral, journalistic tone
6. Do NOT add any commentary, opinions, or fictional content

OUTPUT FORMAT — respond ONLY with valid JSON, no markdown fences, no extra text:
{
  "title": "A clear, engaging title (max 15 words)",
  "content": "The rewritten article text, with 5 key words marked as **word**",
  "summary": "2-3 sentence summary of the article",
  "difficulty_level": "B1" or "B2",
  "highlight_words": ["word1", "word2", "word3", "word4", "word5"]
}
"""

USER_PROMPT_TEMPLATE = """\
Please rewrite the following article for B1-B2 English learners:

TITLE: {title}

CONTENT:
{content}
"""


# ── LLM Clients ───────────────────────────────────────────────────

async def _call_openai(prompt: str) -> str:
    """呼叫 OpenAI Chat Completions API（async httpx，不依賴 openai SDK 版本）"""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set in .env")

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",      # 成本低、速度快，B1-B2 改寫夠用
                "temperature": LLM_TEMPERATURE,
                "max_tokens": LLM_MAX_TOKENS,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def _call_anthropic(prompt: str) -> str:
    """呼叫 Anthropic Messages API（async httpx）"""
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set in .env")

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",  # 速度快、成本低
                "temperature": LLM_TEMPERATURE,
                "max_tokens": LLM_MAX_TOKENS,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]


async def _call_llm(prompt: str) -> str:
    """統一入口：依 config.llm_provider 決定呼叫哪個 API"""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return await _call_openai(prompt)
    elif provider == "anthropic":
        return await _call_anthropic(prompt)
    else:
        raise ValueError(f"Unknown LLM provider: '{provider}'. Use 'openai' or 'anthropic'.")


# ── JSON 解析 ─────────────────────────────────────────────────────

def _parse_llm_response(raw: str) -> dict:
    """
    解析 LLM 回傳的 JSON。
    LLM 有時會加上 ```json ... ``` fence，這裡一律清掉再解析。
    """
    # 移除 markdown code fence（```json ... ``` 或 ``` ... ```）
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = cleaned.rstrip("`").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed. Raw response:\n{raw[:500]}")
        raise ValueError(f"LLM returned invalid JSON: {e}") from e


# ── 品質驗證 ──────────────────────────────────────────────────────

def _validate_output(data: dict) -> list[str]:
    """
    驗證 LLM 輸出品質，回傳錯誤訊息 list。
    空 list 表示通過。
    """
    errors = []

    # 必要欄位存在
    for field in ("title", "content", "summary", "difficulty_level", "highlight_words"):
        if not data.get(field):
            errors.append(f"Missing or empty field: '{field}'")

    if errors:
        return errors

    # 字數檢查
    word_count = len(data["content"].split())
    if word_count < TARGET_WORD_COUNT_MIN:
        errors.append(f"Content too short: {word_count} words (min {TARGET_WORD_COUNT_MIN})")
    if word_count > TARGET_WORD_COUNT_MAX * 1.3:  # 30% 容忍度
        errors.append(f"Content too long: {word_count} words (max ~{TARGET_WORD_COUNT_MAX})")

    # highlight_words 數量
    hw = data["highlight_words"]
    if not isinstance(hw, list) or len(hw) < 3:
        errors.append(f"highlight_words too few: {len(hw) if isinstance(hw, list) else 'not a list'}")

    # difficulty_level 值
    if data["difficulty_level"] not in ("A2", "B1", "B2", "C1"):
        errors.append(f"Invalid difficulty_level: {data['difficulty_level']}")

    # content 裡要有 ** 標記（確認 LLM 有按格式）
    if "**" not in data["content"]:
        errors.append("No **highlighted words** found in content")

    return errors


# ── 主流程 ────────────────────────────────────────────────────────

async def generate_article(raw: RawArticle) -> GeneratedArticle:
    """
    核心函式：接收 RawArticle，呼叫 LLM 改寫，回傳 GeneratedArticle。
    品質不合格時自動重試，超過次數拋出 RuntimeError。

    Args:
        raw: 來自 RSS fetcher 的原始文章

    Returns:
        GeneratedArticle 結構化文章

    Raises:
        RuntimeError: 超過最大重試次數仍不合格
        ValueError: LLM provider 設定錯誤
    """
    prompt = USER_PROMPT_TEMPLATE.format(
        title=raw.title,
        content=raw.raw_content[:3000],  # 限制 input token，避免超過 context window
    )

    last_errors: list[str] = []

    for attempt in range(1, MAX_RETRIES + 2):  # +2 讓最後一次是第 MAX_RETRIES+1 次
        logger.info(
            f"[ArticleGenerator] Attempt {attempt}/{MAX_RETRIES + 1} "
            f"via {settings.llm_provider} — '{raw.title[:50]}'"
        )

        try:
            raw_response = await _call_llm(prompt)
            data = _parse_llm_response(raw_response)
            errors = _validate_output(data)

            if not errors:
                # ✅ 品質通過
                content = data["content"]
                word_count = len(content.split())

                logger.info(
                    f"[ArticleGenerator] Success — "
                    f"{word_count} words, level={data['difficulty_level']}, "
                    f"highlights={data['highlight_words']}"
                )

                return GeneratedArticle(
                    title=data["title"].strip(),
                    content=content.strip(),
                    summary=data["summary"].strip(),
                    difficulty_level=data["difficulty_level"],
                    highlight_words=data["highlight_words"][:HIGHLIGHT_WORD_COUNT],
                    word_count=word_count,
                    source_name=raw.source_name,
                    source_url=raw.source_url,
                    source_title=raw.title,
                )
            else:
                last_errors = errors
                logger.warning(
                    f"[ArticleGenerator] Quality check failed (attempt {attempt}): "
                    + "; ".join(errors)
                )

        except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
            logger.error(f"[ArticleGenerator] HTTP error on attempt {attempt}: {e}")
            last_errors = [str(e)]

        except ValueError as e:
            logger.error(f"[ArticleGenerator] Parse error on attempt {attempt}: {e}")
            last_errors = [str(e)]

    raise RuntimeError(
        f"Article generation failed after {MAX_RETRIES + 1} attempts. "
        f"Last errors: {'; '.join(last_errors)}"
    )
