from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest

from character_quotes.database import (
    begin_daily_assignment,
    initialize,
    make_engine,
    session_factory,
)
from character_quotes.models import QuoteStatus
from character_quotes.service import (
    DuplicateQuoteError,
    ExactTextCollisionError,
    QuoteInput,
    QuoteService,
)


@pytest.fixture()
def service() -> QuoteService:
    engine = make_engine("sqlite://")
    initialize(engine)
    session = session_factory(engine)()
    try:
        yield QuoteService(session)
    finally:
        session.close()
        engine.dispose()


def item(
    text: str = "‘Hello’ — world",
    work: str = "Novel",
    character: str | None = None,
    status: QuoteStatus = QuoteStatus.PUBLISHED,
) -> QuoteInput:
    return QuoteInput(
        text=text, author="A. Author", work=work, character=character, status=status
    )


def test_normalized_same_identity_is_rejected(service: QuoteService) -> None:
    original = service.create(item())
    duplicate = item("  'hello' - world ")
    with pytest.raises(DuplicateQuoteError) as error:
        service.create(duplicate)
    assert error.value.existing_id == original.id


def test_exact_text_different_attribution_requires_override(
    service: QuoteService,
) -> None:
    service.create(item())
    wrong_book = item(work="Wrong book")
    with pytest.raises(ExactTextCollisionError):
        service.create(wrong_book)
    allowed = service.create(item(work="Deliberate reuse"), allow_exact_reuse=True)
    assert allowed.work.title == "Deliberate reuse"


def test_different_character_is_exact_collision(service: QuoteService) -> None:
    service.create(item())
    different_character = item(character="Someone")
    with pytest.raises(ExactTextCollisionError):
        service.create(different_character)


def test_edit_collision_preserves_original(service: QuoteService) -> None:
    first = service.create(item())
    second = service.create(item("Another quote", work="Another book"))
    collision = item(work="Wrong book")
    with pytest.raises(ExactTextCollisionError):
        service.update(second.id, collision)
    assert service.get(second.id).text == "Another quote"
    assert service.get(first.id).work.title == "Novel"


def test_candidates_are_review_only(service: QuoteService) -> None:
    original = service.create(
        item("Tourist Rincewind had decided meant idiot on the Discworld.")
    )
    candidates = service.candidates(
        "Tourist Rincewind had decided meant idiot the Discworld"
    )
    assert candidates and candidates[0]["quote"]["id"] == original.id
    assert len(service.list()) == 1


def test_daily_assignment_is_stable_and_recycles_after_cycle(
    service: QuoteService,
) -> None:
    first, second = (
        service.create(item("One")),
        service.create(item("Two", work="Second")),
    )
    service.session.commit()
    day_one = service.ensure_daily_assignment(date(2026, 7, 29))
    service.session.commit()
    assert service.ensure_daily_assignment(date(2026, 7, 29)).id == day_one.id
    day_two = service.ensure_daily_assignment(date(2026, 7, 30))
    service.session.commit()
    assert day_two.id != day_one.id
    recycled = service.ensure_daily_assignment(date(2026, 7, 31))
    assert recycled.id in {first.id, second.id}


def test_no_published_quote_cannot_be_assigned(service: QuoteService) -> None:
    service.create(item(status=QuoteStatus.DRAFT))
    with pytest.raises(LookupError):
        service.ensure_daily_assignment(date(2026, 7, 29))


def test_daily_assignment_serializes_concurrent_requests(tmp_path: Path) -> None:
    database = tmp_path / "daily.sqlite3"
    engine = make_engine(str(database))
    initialize(engine)
    db = session_factory(engine)()
    catalogue = QuoteService(db)
    catalogue.create(item("One"))
    catalogue.create(item("Two", work="Second"))
    db.commit()
    db.close()

    def assign(day: date) -> str:
        worker_engine = make_engine(str(database))
        worker_db = session_factory(worker_engine)()
        try:
            begin_daily_assignment(worker_db)
            quote = QuoteService(worker_db).ensure_daily_assignment(day)
            worker_db.commit()
            return quote.id
        finally:
            worker_db.close()
            worker_engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        same_day = list(executor.map(assign, [date(2026, 7, 29)] * 2))
    assert same_day[0] == same_day[1]
    with ThreadPoolExecutor(max_workers=2) as executor:
        distinct_days = list(
            executor.map(assign, [date(2026, 7, 30), date(2026, 7, 31)])
        )
    assert distinct_days[0] != distinct_days[1]
    engine.dispose()
