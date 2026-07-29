from pathlib import Path

from typer.testing import CliRunner

from character_quotes.cli import app


def test_cli_add_check_and_daily(monkeypatch: object, tmp_path: Path) -> None:
    monkeypatch.setenv("CHARACTER_QUOTES_DATABASE", str(tmp_path / "quotes.sqlite3"))  # type: ignore[attr-defined]
    runner = CliRunner()
    added = runner.invoke(
        app,
        [
            "add",
            "One quote",
            "--author",
            "Author",
            "--work",
            "Work",
            "--status",
            "published",
        ],
    )
    assert added.exit_code == 0
    assert runner.invoke(app, ["check", "One quote"]).exit_code == 0
    assert runner.invoke(app, ["daily", "--date", "2026-07-29"]).exit_code == 0
