import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import datetime, date
from .base import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)

    # 原始來源資訊
    source_title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    source_url: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    source_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)  # "BBC", "NPR" 等

    # AI 改寫後內容
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    summary: Mapped[str] = mapped_column(sa.String(500), nullable=True)  # 2-3句摘要

    # 學習相關
    difficulty_level: Mapped[str] = mapped_column(sa.String(10), default="B1")  # A1~C2
    word_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    # 系統標記的學習重點單字，JSON array 格式: ["resilience", "innovation", ...]
    highlight_words: Mapped[str] = mapped_column(sa.Text, default="[]")

    # 排程控制
    publish_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    is_published: Mapped[bool] = mapped_column(sa.Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.func.now())

    # Relationships
    vocab_entries: Mapped[list["VocabEntry"]] = relationship(
        "VocabEntry", back_populates="article", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Article id={self.id} date={self.publish_date} title={self.title[:30]}>"
