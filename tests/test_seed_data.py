import json
from pathlib import Path

from character_quotes.normalization import fingerprint


def test_public_domain_seed_is_import_ready_and_unique() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "public-domain-seed.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert len(payload["quotes"]) >= 9
    assert all(item["status"] == "published" for item in payload["quotes"])
    assert all({"text", "author", "work"} <= item.keys() for item in payload["quotes"])
    assert all(
        all(
            isinstance(item[key], str) and item[key].strip()
            for key in ("text", "author", "work")
        )
        for item in payload["quotes"]
    )
    assert all(
        item["source_url"].startswith("https://www.gutenberg.org/")
        for item in payload["quotes"]
    )
    assert len({fingerprint(item["text"]) for item in payload["quotes"]}) == len(
        payload["quotes"]
    )
