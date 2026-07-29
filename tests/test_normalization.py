import pytest

from character_quotes.database import make_engine
from character_quotes.normalization import fingerprint, normalize


def test_equivalent_punctuation_and_whitespace_match() -> None:
    assert normalize("  ‘Hello’ — world  ") == normalize("'hello' - world")
    assert fingerprint("Hello, world!") == fingerprint("hello world")
    assert fingerprint("café") == fingerprint("cafe\u0301")
    assert fingerprint("under_score") == fingerprint("under score")


def test_only_sqlite_urls_are_allowed() -> None:
    with pytest.raises(ValueError, match="only SQLite"):
        make_engine("postgresql://example.invalid/quotes")
    engine = make_engine("sqlite+pysqlite://")
    try:
        assert engine.dialect.name == "sqlite"
    finally:
        engine.dispose()
