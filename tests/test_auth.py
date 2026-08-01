from __future__ import annotations

from pathlib import Path

from pytest import CaptureFixture, MonkeyPatch

from character_quotes.auth import (
    AUTH_ENABLED,
    VERIFIER_FILE,
    SearchAuth,
    TokenVerifier,
)


def test_generated_search_token_is_printed_once_and_only_its_verifier_persists(
    monkeypatch: MonkeyPatch, tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    verifier_path = tmp_path / "configuration" / "search-token.verifier"
    monkeypatch.setenv(AUTH_ENABLED, "true")
    monkeypatch.setenv(VERIFIER_FILE, str(verifier_path))

    generated = SearchAuth.from_environment()
    token = (
        capsys.readouterr()
        .out.removeprefix("Generated search Bearer token (shown once; save it now): ")
        .strip()
    )

    assert token
    assert generated.matches(token)
    assert token not in verifier_path.read_text(encoding="ascii")
    assert verifier_path.stat().st_mode & 0o777 == 0o600
    assert not TokenVerifier.from_token("another-token").write_new(verifier_path)

    restarted = SearchAuth.from_environment()
    assert capsys.readouterr().out == ""
    assert restarted.matches(token)


def test_explicit_search_token_does_not_create_a_verifier(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    verifier_path = tmp_path / "search-token.verifier"
    monkeypatch.setenv(AUTH_ENABLED, "true")
    monkeypatch.setenv("CHARACTER_QUOTES_SEARCH_BEARER_TOKEN", "secret")
    monkeypatch.setenv(VERIFIER_FILE, str(verifier_path))

    auth = SearchAuth.from_environment()

    assert auth.matches("secret")
    assert not auth.matches("wrong")
    assert not verifier_path.exists()
