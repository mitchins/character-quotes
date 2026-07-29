"""Transaction-neutral catalogue operations shared by API and CLI."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from urllib.parse import urlparse

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from .models import Author, DailyAssignment, Quote, QuoteStatus, Work
from .normalization import fingerprint, normalize, token_signature


class DuplicateQuoteError(ValueError):
    def __init__(self, existing_id: str) -> None:
        super().__init__(f"Exact duplicate of quote {existing_id}")
        self.existing_id = existing_id


class ExactTextCollisionError(ValueError):
    def __init__(self, existing_ids: list[str]) -> None:
        super().__init__("Exact quote text already exists with different attribution")
        self.existing_ids = existing_ids


@dataclass(frozen=True)
class QuoteInput:
    text: str
    author: str
    work: str
    character: str | None = None
    series: str | None = None
    citation: str | None = None
    source_url: str | None = None
    status: QuoteStatus = QuoteStatus.DRAFT


def utc_string(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def serialize(quote: Quote) -> dict[str, object]:
    return {
        "id": quote.id,
        "text": quote.text,
        "character": quote.character_name,
        "author": quote.work.author.name,
        "work": quote.work.title,
        "series": quote.work.series,
        "citation": quote.citation,
        "source_url": quote.source_url,
        "status": quote.status,
        "created_at": utc_string(quote.created_at),
        "updated_at": utc_string(quote.updated_at),
    }


def _word_jaccard(left: str, right: str) -> float:
    left_tokens, right_tokens = token_signature(left), token_signature(right)
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 0.0


def _trigram_dice(left: str, right: str) -> float:
    def trigrams(value: str) -> set[str]:
        padded = f"  {value}  "
        return {padded[index : index + 3] for index in range(len(padded) - 2)}

    left_grams, right_grams = trigrams(normalize(left)), trigrams(normalize(right))
    return 2 * len(left_grams & right_grams) / (len(left_grams) + len(right_grams))


class QuoteService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _author(self, name: str) -> Author:
        key = normalize(name)
        author = self.session.scalar(
            select(Author).where(Author.normalized_name == key)
        )
        if author is None:
            author = Author(name=name.strip(), normalized_name=key)
            self.session.add(author)
            self.session.flush()
        return author

    def _work(self, title: str, author: Author, series: str | None) -> Work:
        key = normalize(title)
        work = self.session.scalar(
            select(Work).where(
                Work.normalized_title == key, Work.author_id == author.id
            )
        )
        if work is None:
            work = Work(
                title=title.strip(),
                normalized_title=key,
                author_id=author.id,
                series=series,
            )
            self.session.add(work)
            self.session.flush()
        return work

    def _validate(self, data: QuoteInput) -> None:
        if not all(normalize(value) for value in (data.text, data.author, data.work)):
            raise ValueError("text, author, and work are required")
        if data.source_url:
            parsed = urlparse(data.source_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("source_url must be an absolute http(s) URL")

    def _quotes(self, statement: Select[tuple[Quote]]) -> list[Quote]:
        return list(
            self.session.scalars(
                statement.options(joinedload(Quote.work).joinedload(Work.author))
            )
        )

    def _check_collision(
        self, data: QuoteInput, exclude_id: str | None, allow_exact_reuse: bool
    ) -> None:
        character_key = normalize(data.character) if data.character else "__none__"
        work_key, author_key = normalize(data.work), normalize(data.author)
        matches = self._quotes(
            select(Quote).where(Quote.text_fingerprint == fingerprint(data.text))
        )
        matches = [quote for quote in matches if quote.id != exclude_id]
        same_identity = next(
            (
                quote
                for quote in matches
                if quote.normalized_character == character_key
                and quote.work.normalized_title == work_key
                and quote.work.author.normalized_name == author_key
            ),
            None,
        )
        if same_identity:
            raise DuplicateQuoteError(same_identity.id)
        if matches and not allow_exact_reuse:
            raise ExactTextCollisionError([quote.id for quote in matches])

    def create(self, data: QuoteInput, *, allow_exact_reuse: bool = False) -> Quote:
        self._validate(data)
        self._check_collision(data, None, allow_exact_reuse)
        author = self._author(data.author)
        work = self._work(data.work, author, data.series)
        quote = Quote(
            text=data.text.strip(),
            normalized_text=normalize(data.text),
            text_fingerprint=fingerprint(data.text),
            character_name=data.character,
            normalized_character=normalize(data.character)
            if data.character
            else "__none__",
            work_id=work.id,
            citation=data.citation,
            source_url=data.source_url,
            status=data.status.value,
        )
        self.session.add(quote)
        self.session.flush()
        return self.get(quote.id)

    def update(
        self, quote_id: str, data: QuoteInput, *, allow_exact_reuse: bool = False
    ) -> Quote:
        self._validate(data)
        quote = self.get(quote_id)
        self._check_collision(data, quote.id, allow_exact_reuse)
        author = self._author(data.author)
        work = self._work(data.work, author, data.series)
        quote.text, quote.normalized_text, quote.text_fingerprint = (
            data.text.strip(),
            normalize(data.text),
            fingerprint(data.text),
        )
        quote.character_name = data.character
        quote.normalized_character = (
            normalize(data.character) if data.character else "__none__"
        )
        quote.work_id, quote.citation, quote.source_url, quote.status = (
            work.id,
            data.citation,
            data.source_url,
            data.status.value,
        )
        self.session.flush()
        return self.get(quote.id)

    def get(self, quote_id: str) -> Quote:
        quote = self.session.scalar(
            select(Quote)
            .options(joinedload(Quote.work).joinedload(Work.author))
            .where(Quote.id == quote_id)
        )
        if quote is None:
            raise LookupError(quote_id)
        return quote

    def list(self, status: QuoteStatus | None = None) -> list[Quote]:
        statement: Select[tuple[Quote]] = select(Quote).order_by(
            Quote.created_at, Quote.id
        )
        if status:
            statement = statement.where(Quote.status == status.value)
        return self._quotes(statement)

    def collisions(self, text: str) -> Sequence[Quote]:
        return self._quotes(
            select(Quote).where(Quote.text_fingerprint == fingerprint(text))
        )

    def candidates(self, text: str, limit: int = 20) -> Sequence[dict[str, object]]:
        if not 0 <= limit <= 20:
            raise ValueError("limit must be between 0 and 20")
        tokens = token_signature(text)
        results: list[tuple[float, float, dict[str, object]]] = []
        for quote in self.list():
            shared = len(tokens & token_signature(quote.text))
            word_score, trigram_score = (
                _word_jaccard(text, quote.text),
                _trigram_dice(text, quote.text),
            )
            if (shared >= 5 and word_score >= 0.75) or trigram_score >= 0.88:
                results.append(
                    (
                        word_score,
                        trigram_score,
                        {
                            "quote": serialize(quote),
                            "shared_tokens": shared,
                            "word_jaccard": round(word_score, 3),
                            "trigram_dice": round(trigram_score, 3),
                        },
                    )
                )
        ordered = sorted(
            results, key=lambda item: (-item[1], -item[0], str(item[2]["quote"]))
        )
        return [item[2] for item in ordered[:limit]]

    def ensure_daily_assignment(self, selected_date: date) -> Quote:
        existing = self.session.scalar(
            select(DailyAssignment)
            .options(
                joinedload(DailyAssignment.quote)
                .joinedload(Quote.work)
                .joinedload(Work.author)
            )
            .where(DailyAssignment.selected_date == selected_date)
        )
        if existing:
            return existing.quote
        eligible = self.list(QuoteStatus.PUBLISHED)
        if not eligible:
            raise LookupError("No published quotes available")
        recent = self.session.scalars(
            select(DailyAssignment.quote_id)
            .join(Quote)
            .where(Quote.status == QuoteStatus.PUBLISHED.value)
            .order_by(DailyAssignment.assigned_at.desc(), DailyAssignment.id.desc())
            .limit(max(len(eligible) - 1, 0))
        ).all()
        candidates = [
            quote for quote in eligible if quote.id not in set(recent)
        ] or eligible
        chosen = max(
            candidates,
            key=lambda quote: hashlib.sha256(
                f"{selected_date}:{quote.id}".encode()
            ).digest(),
        )
        self.session.add(
            DailyAssignment(selected_date=selected_date, quote_id=chosen.id)
        )
        self.session.flush()
        return chosen
