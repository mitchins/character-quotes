"""Terminal curation interface."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy.exc import IntegrityError

from .database import (
    begin_catalogue_mutation,
    begin_daily_assignment,
    initialize,
    make_engine,
    session_factory,
)
from .models import Quote, QuoteStatus
from .service import (
    DuplicateQuoteError,
    ExactTextCollisionError,
    QuoteInput,
    QuoteService,
    serialize,
)

app = typer.Typer(
    no_args_is_help=True, help="Curate and serve fictional-character quotes."
)


def run_mutation(operation: Callable[[QuoteService], Quote]) -> dict[str, object]:
    engine = make_engine()
    initialize(engine)
    db = session_factory(engine)()
    try:
        begin_catalogue_mutation(db)
        result = operation(QuoteService(db))
        db.commit()
        return serialize(result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        engine.dispose()


def quote_input(
    text: str,
    author: str,
    work: str,
    character: str | None,
    series: str | None,
    citation: str | None,
    source_url: str | None,
    quote_status: QuoteStatus,
) -> QuoteInput:
    return QuoteInput(
        text=text,
        author=author,
        work=work,
        character=character,
        series=series,
        citation=citation,
        source_url=source_url,
        status=quote_status,
    )


@app.command()
def init() -> None:
    engine = make_engine()
    try:
        initialize(engine)
    finally:
        engine.dispose()
    typer.echo("Catalogue ready")


@app.command()
def add(
    text: str,
    author: Annotated[str, typer.Option()],
    work: Annotated[str, typer.Option()],
    character: Annotated[str | None, typer.Option()] = None,
    series: Annotated[str | None, typer.Option()] = None,
    citation: Annotated[str | None, typer.Option()] = None,
    source_url: Annotated[str | None, typer.Option()] = None,
    quote_status: Annotated[QuoteStatus, typer.Option("--status")] = QuoteStatus.DRAFT,
    allow_exact_reuse: bool = False,
) -> None:
    """Add a quote; cross-attribution exact matches require an explicit override."""
    data = quote_input(
        text, author, work, character, series, citation, source_url, quote_status
    )
    try:
        typer.echo(
            json.dumps(
                run_mutation(
                    lambda catalogue: catalogue.create(
                        data, allow_exact_reuse=allow_exact_reuse
                    )
                ),
                indent=2,
            )
        )
    except DuplicateQuoteError as error:
        typer.echo(f"Duplicate: {error.existing_id}", err=True)
        raise typer.Exit(2) from error
    except ExactTextCollisionError as error:
        typer.echo(
            "Exact text collision: "
            f"{', '.join(error.existing_ids)}; use --allow-exact-reuse if deliberate",
            err=True,
        )
        raise typer.Exit(2) from error


@app.command("check")
def check_quote(text: str) -> None:
    """Show exact-text collisions and review-only similar candidates."""
    engine = make_engine()
    initialize(engine)
    db = session_factory(engine)()
    try:
        catalogue = QuoteService(db)
        typer.echo(
            json.dumps(
                {
                    "exact": [serialize(item) for item in catalogue.collisions(text)],
                    "candidates": catalogue.candidates(text),
                },
                indent=2,
            )
        )
    finally:
        db.close()
        engine.dispose()


@app.command("list")
def list_quotes(quote_status: QuoteStatus | None = None) -> None:
    engine = make_engine()
    initialize(engine)
    db = session_factory(engine)()
    try:
        typer.echo(
            json.dumps(
                [serialize(item) for item in QuoteService(db).list(quote_status)],
                indent=2,
            )
        )
    finally:
        db.close()
        engine.dispose()


@app.command()
def daily(selected_date: Annotated[str | None, typer.Option("--date")] = None) -> None:
    """Return or lazily assign the quote for a day."""
    try:
        requested = date.fromisoformat(selected_date) if selected_date else date.today()
    except ValueError as error:
        raise typer.BadParameter("--date must be an ISO date (YYYY-MM-DD)") from error
    engine = make_engine()
    initialize(engine)
    db = session_factory(engine)()
    try:
        begin_daily_assignment(db)
        result = serialize(QuoteService(db).ensure_daily_assignment(requested))
        db.commit()
    except LookupError as error:
        db.rollback()
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    finally:
        db.close()
        engine.dispose()
    result["selected_for_date"] = requested.isoformat()
    typer.echo(json.dumps(result, indent=2))


@app.command()
def export(path: Path) -> None:
    """Export simple JSON interchange (not a backup format)."""
    engine = make_engine()
    initialize(engine)
    db = session_factory(engine)()
    try:
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "quotes": [serialize(item) for item in QuoteService(db).list()],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    finally:
        db.close()
        engine.dispose()


@app.command()
def import_json(path: Path, dry_run: bool = False) -> None:
    """Import JSON interchange transactionally."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or not isinstance(payload.get("quotes"), list)
        ):
            raise ValueError
        if not all(
            isinstance(item, dict) and {"text", "author", "work"} <= item.keys()
            for item in payload["quotes"]
        ):
            raise ValueError
    except (json.JSONDecodeError, OSError, ValueError) as error:
        raise typer.BadParameter("expected JSON schema_version 1") from error
    engine = make_engine()
    initialize(engine)
    db = session_factory(engine)()
    try:
        begin_catalogue_mutation(db)
        catalogue = QuoteService(db)
        for item in payload["quotes"]:
            catalogue.create(
                QuoteInput(
                    text=item["text"],
                    author=item["author"],
                    work=item["work"],
                    character=item.get("character"),
                    series=item.get("series"),
                    citation=item.get("citation"),
                    source_url=item.get("source_url"),
                    status=QuoteStatus(item.get("status", "draft")),
                ),
                allow_exact_reuse=True,
            )
        if dry_run:
            db.rollback()
        else:
            db.commit()
    except (ValueError, IntegrityError):
        db.rollback()
        raise
    finally:
        db.close()
        engine.dispose()
