"""
API Schemas（Pydantic models）
Request / Response 的資料結構定義
"""
import json
from datetime import date, datetime
from pydantic import BaseModel, field_validator


# ── Article ──────────────────────────────────────────────────────

class ArticleResponse(BaseModel):
    """單篇文章的完整回應"""
    id: int
    title: str
    content: str
    summary: str | None
    difficulty_level: str
    highlight_words: list[str]   # 從 JSON string 轉成 list
    word_count: int
    publish_date: date
    source_name: str
    source_url: str
    source_title: str
    created_at: datetime

    @field_validator("highlight_words", mode="before")
    @classmethod
    def parse_highlight_words(cls, v):
        """DB 裡存的是 JSON string，轉成 list"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []

    model_config = {"from_attributes": True}


class ArticleListItem(BaseModel):
    """文章列表用的精簡版（不含全文）"""
    id: int
    title: str
    summary: str | None
    difficulty_level: str
    word_count: int
    publish_date: date
    source_name: str

    model_config = {"from_attributes": True}


class GenerateTodayResponse(BaseModel):
    """手動觸發文章生成的回應"""
    message: str
    article_id: int
    title: str
    word_count: int
    difficulty_level: str
    highlight_words: list[str]
