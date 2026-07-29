"""Small versioned REST API; transaction ownership lives at this boundary."""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import begin_daily_assignment, initialize, make_engine, session_factory
from .models import Quote, QuoteStatus
from .service import (
    DuplicateQuoteError,
    ExactTextCollisionError,
    QuoteInput,
    QuoteService,
    serialize,
)

engine = make_engine()
initialize(engine)
SessionLocal = session_factory(engine)
app = FastAPI(title="Character Quotes", version="0.2.0")


class QuotePayload(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    author: str = Field(min_length=1, max_length=300)
    work: str = Field(min_length=1, max_length=500)
    character: str | None = Field(default=None, max_length=300)
    series: str | None = Field(default=None, max_length=300)
    citation: str | None = Field(default=None, max_length=1000)
    source_url: HttpUrl | None = None
    status: QuoteStatus = QuoteStatus.DRAFT

    def as_input(self) -> QuoteInput:
        return QuoteInput(
            **self.model_dump(exclude={"source_url"}),
            source_url=str(self.source_url) if self.source_url else None,
        )


def session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def mutation(operation: Callable[[], Quote], db: Session) -> dict[str, object]:
    try:
        result = operation()
        db.commit()
        return serialize(result)
    except DuplicateQuoteError as error:
        db.rollback()
        raise HTTPException(
            409, {"message": str(error), "existing_id": error.existing_id}
        ) from error
    except ExactTextCollisionError as error:
        db.rollback()
        raise HTTPException(
            409,
            {
                "message": str(error),
                "existing_ids": error.existing_ids,
                "allow_exact_reuse": True,
            },
        ) from error
    except LookupError as error:
        db.rollback()
        raise HTTPException(404, "Quote not found") from error
    except (ValueError, IntegrityError) as error:
        db.rollback()
        raise HTTPException(422, str(error)) from error


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/quotes", status_code=status.HTTP_201_CREATED)
def create_quote(
    payload: QuotePayload,
    db: Annotated[Session, Depends(session)],
    allow_exact_reuse: bool = False,
) -> dict[str, object]:
    return mutation(
        lambda: QuoteService(db).create(
            payload.as_input(), allow_exact_reuse=allow_exact_reuse
        ),
        db,
    )


@app.get("/v1/quotes")
def list_quotes(
    db: Annotated[Session, Depends(session)],
    quote_status: QuoteStatus | None = Query(default=None, alias="status"),
) -> list[dict[str, object]]:
    return [serialize(quote) for quote in QuoteService(db).list(quote_status)]


@app.get("/v1/quotes/duplicates")
def duplicate_quotes(
    text: str, db: Annotated[Session, Depends(session)]
) -> list[dict[str, object]]:
    return [serialize(quote) for quote in QuoteService(db).collisions(text)]


@app.get("/v1/quotes/candidates")
def candidate_quotes(
    text: str, db: Annotated[Session, Depends(session)]
) -> list[dict[str, object]]:
    return list(QuoteService(db).candidates(text))


@app.get("/v1/quotes/daily")
def daily_quote(
    db: Annotated[Session, Depends(session)],
    selected_date: date = Query(default_factory=date.today),
) -> dict[str, object]:
    try:
        begin_daily_assignment(db)
        result = QuoteService(db).ensure_daily_assignment(selected_date)
        db.commit()
    except LookupError as error:
        db.rollback()
        raise HTTPException(404, str(error)) from error
    response = serialize(result)
    response["selected_for_date"] = selected_date.isoformat()
    return response


@app.get("/v1/quotes/{quote_id}")
def get_quote(
    quote_id: str, db: Annotated[Session, Depends(session)]
) -> dict[str, object]:
    try:
        return serialize(QuoteService(db).get(quote_id))
    except LookupError as error:
        raise HTTPException(404, "Quote not found") from error


@app.patch("/v1/quotes/{quote_id}")
def update_quote(
    quote_id: str,
    payload: QuotePayload,
    db: Annotated[Session, Depends(session)],
    allow_exact_reuse: bool = False,
) -> dict[str, object]:
    return mutation(
        lambda: QuoteService(db).update(
            quote_id, payload.as_input(), allow_exact_reuse=allow_exact_reuse
        ),
        db,
    )
