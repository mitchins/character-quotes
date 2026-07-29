import json
from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from character_quotes.cli import app


def test_cli_add_check_and_daily(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHARACTER_QUOTES_DATABASE", str(tmp_path / "quotes.sqlite3"))
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


def test_cli_import_reused_text_and_rejects_invalid_payload(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CHARACTER_QUOTES_DATABASE", str(tmp_path / "quotes.sqlite3"))
    valid = tmp_path / "quotes.json"
    valid.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "quotes": [
                    {"text": "A reused quote", "author": "Author", "work": "Work"},
                    {
                        "text": "A reused quote",
                        "author": "Other author",
                        "work": "Other work",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not json", encoding="utf-8")
    runner = CliRunner()
    assert runner.invoke(app, ["import-json", str(valid)]).exit_code == 0
    listed = runner.invoke(app, ["list"])
    assert listed.exit_code == 0
    assert len(json.loads(listed.output)) == 2
    bad_import = runner.invoke(app, ["import-json", str(invalid)])
    assert bad_import.exit_code == 2
    assert "expected JSON schema_version 1" in bad_import.output
    bad_date = runner.invoke(app, ["daily", "--date", "not-a-date"])
    assert bad_date.exit_code == 2
    assert "--date must be an ISO date" in bad_date.output
