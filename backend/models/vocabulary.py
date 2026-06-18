import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import datetime
from .base import Base


class VocabEntry(Base):
    __tablename__ = "vocab_entries"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)

    # 外鍵
    user_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )

    # 單字資料
    word: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    # 使用者查詢時的原始句子 context（方便複習）
    context_sentence: Mapped[str] = mapped_column(sa.Text, nullable=True)

    # 快取的字典資料（避免每次都打外部 API）
    # JSON 格式: {"phonetic": "...", "partOfSpeech": "...", "definition": "...", "example": "..."}
    cached_definition: Mapped[str] = mapped_column(sa.Text, nullable=True)

    # 複習狀態（未來可擴充 SRS 間隔複習）
    review_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    last_reviewed_at: Mapped[datetime] = mapped_column(sa.DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.func.now())

    # Unique constraint：同個 user 同個單字只存一次
    __table_args__ = (
        sa.UniqueConstraint("user_id", "word", name="uq_user_word"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="vocab_entries")
    article: Mapped["Article"] = relationship("Article", back_populates="vocab_entries")

    def __repr__(self) -> str:
        return f"<VocabEntry user_id={self.user_id} word={self.word}>"
