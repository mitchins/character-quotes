from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from character_quotes import api
from character_quotes.auth import SearchAuth
from character_quotes.database import initialize, make_engine, session_factory


def test_routes_duplicate_collision_and_stable_timestamps(
    monkeypatch: MonkeyPatch,
) -> None:
    engine = make_engine("sqlite://")
    initialize(engine)
    monkeypatch.setattr(api, "SessionLocal", session_factory(engine))
    client = TestClient(api.app)
    payload = {
        "text": "A quote",
        "author": "Author",
        "work": "Work",
        "status": "published",
    }
    created = client.post("/v1/quotes", json=payload)
    assert created.status_code == 201
    quote = created.json()
    assert quote["created_at"].endswith("Z")
    assert (
        client.get("/v1/quotes/duplicates", params={"text": "A quote"}).json()[0]["id"]
        == quote["id"]
    )
    assert (
        client.post("/v1/quotes", json={**payload, "work": "Wrong Work"}).status_code
        == 409
    )
    assert (
        client.get(f"/v1/quotes/{quote['id']}").json()["created_at"]
        == quote["created_at"]
    )


def test_api_candidates_update_and_empty_daily_error(monkeypatch: MonkeyPatch) -> None:
    engine = make_engine("sqlite://")
    initialize(engine)
    monkeypatch.setattr(api, "SessionLocal", session_factory(engine))
    client = TestClient(api.app)
    assert client.get("/v1/quotes/daily").status_code == 404
    created = client.post(
        "/v1/quotes",
        json={
            "text": "Five words make candidate matching easy",
            "author": "A",
            "work": "W",
        },
    ).json()
    assert (
        client.get(
            "/v1/quotes/candidates",
            params={"text": "Five words make candidate matching"},
        ).status_code
        == 200
    )
    updated = client.patch(
        f"/v1/quotes/{created['id']}",
        json={
            "text": "Five words make candidate matching easy",
            "author": "A",
            "work": "W",
            "status": "published",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "published"


def test_patch_missing_quote_returns_not_found(monkeypatch: MonkeyPatch) -> None:
    engine = make_engine("sqlite://")
    initialize(engine)
    monkeypatch.setattr(api, "SessionLocal", session_factory(engine))
    response = TestClient(api.app).patch(
        "/v1/quotes/not-a-real-id",
        json={"text": "Text", "author": "Author", "work": "Work"},
    )
    assert response.status_code == 404


def test_search_routes_require_bearer_but_daily_does_not(
    monkeypatch: MonkeyPatch,
) -> None:
    engine = make_engine("sqlite://")
    initialize(engine)
    monkeypatch.setattr(api, "SessionLocal", session_factory(engine))
    monkeypatch.setattr(api, "search_auth", SearchAuth(None, "search-token"))
    client = TestClient(api.app)

    assert client.get("/v1/quotes").status_code == 401
    assert client.get("/v1/quotes").headers["www-authenticate"] == "Bearer"
    assert client.get("/v1/quotes/daily").status_code == 404
    assert client.get(
        "/v1/quotes/check",
        params={"text": "A quote"},
        headers={"Authorization": "Bearer search-token"},
    ).json() == {"exact": [], "candidates": []}


def test_http_writes_can_be_disabled_for_container_deployment(
    monkeypatch: MonkeyPatch,
) -> None:
    engine = make_engine("sqlite://")
    initialize(engine)
    monkeypatch.setattr(api, "SessionLocal", session_factory(engine))
    monkeypatch.setenv("CHARACTER_QUOTES_HTTP_WRITES", "false")

    response = TestClient(api.app).post(
        "/v1/quotes", json={"text": "Text", "author": "Author", "work": "Work"}
    )

    assert response.status_code == 405


def test_enabled_http_writes_still_require_bearer(monkeypatch: MonkeyPatch) -> None:
    engine = make_engine("sqlite://")
    initialize(engine)
    monkeypatch.setattr(api, "SessionLocal", session_factory(engine))
    monkeypatch.setattr(api, "search_auth", SearchAuth(None, "search-token"))
    monkeypatch.setenv("CHARACTER_QUOTES_HTTP_WRITES", "true")
    client = TestClient(api.app)
    payload = {"text": "Text", "author": "Author", "work": "Work"}

    assert client.post("/v1/quotes", json=payload).status_code == 401
    assert (
        client.post(
            "/v1/quotes",
            json=payload,
            headers={"Authorization": "Bearer search-token"},
        ).status_code
        == 201
    )
