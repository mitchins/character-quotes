from character_quotes.normalization import fingerprint, normalize


def test_equivalent_punctuation_and_whitespace_match() -> None:
    assert normalize("  ‘Hello’ — world  ") == normalize("'hello' - world")
    assert fingerprint("Hello, world!") == fingerprint("hello world")
    assert fingerprint("café") == fingerprint("cafe\u0301")
