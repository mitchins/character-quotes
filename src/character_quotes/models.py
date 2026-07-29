"""Lean persistent catalogue models."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class QuoteStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Author(Base):
    __tablename__ = "authors"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(300), unique=True)
    normalized_name: Mapped[str] = mapped_column(String(300), unique=True, index=True)


class Work(Base):
    __tablename__ = "works"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    title: Mapped[str] = mapped_column(String(500))
    normalized_title: Mapped[str] = mapped_column(String(500), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.id"), index=True)
    series: Mapped[str | None] = mapped_column(String(300), nullable=True)
    author: Mapped[Author] = relationship()
    __table_args__ = (
        UniqueConstraint("normalized_title", "author_id", name="uq_work_title_author"),
    )


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text, index=True)
    text_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    character_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    normalized_character: Mapped[str] = mapped_column(String(300), default="__none__")
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    citation: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default=QuoteStatus.DRAFT.value, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    work: Mapped[Work] = relationship()
    assignments: Mapped[list[DailyAssignment]] = relationship()
    __table_args__ = (
        UniqueConstraint(
            "normalized_text",
            "normalized_character",
            "work_id",
            name="uq_quote_identity",
        ),
    )


class DailyAssignment(Base):
    __tablename__ = "daily_assignments"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    selected_date: Mapped[date] = mapped_column(Date, unique=True)
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"), index=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    quote: Mapped[Quote] = relationship(back_populates="assignments")
