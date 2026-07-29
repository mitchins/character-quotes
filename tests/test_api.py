from fastapi.testclient import TestClient

from character_quotes import api
from character_quotes.database import initialize, make_engine, session_factory


def test_routes_duplicate_collision_and_stable_timestamps() -> None:
    engine = make_engine("sqlite://")
    initialize(engine)
    original = api.SessionLocal
    api.SessionLocal = session_factory(engine)
    try:
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
            client.get("/v1/quotes/duplicates", params={"text": "A quote"}).json()[0][
                "id"
            ]
            == quote["id"]
        )
        conflict = client.post("/v1/quotes", json={**payload, "work": "Wrong Work"})
        assert conflict.status_code == 409
        assert (
            client.get(f"/v1/quotes/{quote['id']}").json()["created_at"]
            == quote["created_at"]
        )
    finally:
        api.SessionLocal = original


def test_api_candidates_update_and_empty_daily_error() -> None:
    engine = make_engine("sqlite://")
    initialize(engine)
    original = api.SessionLocal
    api.SessionLocal = session_factory(engine)
    try:
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
    finally:
        api.SessionLocal = original


def test_patch_missing_quote_returns_not_found() -> None:
    engine = make_engine("sqlite://")
    initialize(engine)
    original = api.SessionLocal
    api.SessionLocal = session_factory(engine)
    try:
        response = TestClient(api.app).patch(
            "/v1/quotes/not-a-real-id",
            json={"text": "Text", "author": "Author", "work": "Work"},
        )
        assert response.status_code == 404
    finally:
        api.SessionLocal = original
