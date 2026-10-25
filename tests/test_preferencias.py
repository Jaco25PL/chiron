"""/api/preferencias: the accent color each user picks in the user menu (in memory: no DATABASE_URL)."""

import os
import time

os.environ["CHIRON_FAKE"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from api.security import sign  # noqa: E402
from store import db  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    db._acentos.clear()
    yield
    db._acentos.clear()


def as_user(email: str) -> dict:
    return {"x-chiron-user": email}


def test_default_is_menta():
    r = client.get("/api/preferencias", headers=as_user("nueva@example.com"))
    assert r.status_code == 200
    assert r.json() == {"acento": "menta"}


def test_set_and_read_back():
    r = client.post("/api/preferencias", json={"acento": "rosa"}, headers=as_user("ana@example.com"))
    assert r.status_code == 200
    assert r.json() == {"acento": "rosa"}
    assert client.get("/api/preferencias", headers=as_user("ana@example.com")).json() == {"acento": "rosa"}


@pytest.mark.parametrize("body", [{"acento": "verde"}, {"acento": ""}, {}, {"acento": 3}])
def test_invalid_values_are_rejected(body):
    r = client.post("/api/preferencias", json=body, headers=as_user("ana@example.com"))
    assert r.status_code in (400, 422)
    assert "error" in r.json()
    assert client.get("/api/preferencias", headers=as_user("ana@example.com")).json() == {"acento": "menta"}


def test_each_user_has_their_own():
    client.post("/api/preferencias", json={"acento": "azul"}, headers=as_user("ana@example.com"))
    client.post("/api/preferencias", json={"acento": "gris"}, headers=as_user("beto@example.com"))
    assert client.get("/api/preferencias", headers=as_user("ana@example.com")).json() == {"acento": "azul"}
    assert client.get("/api/preferencias", headers=as_user("beto@example.com")).json() == {"acento": "gris"}


def test_signed_identity_is_required_when_a_secret_is_set(monkeypatch):
    monkeypatch.setenv("CHIRON_BACKEND_SECRET", "s")
    assert client.get("/api/preferencias", headers=as_user("ana@example.com")).status_code == 401

    ts = str(int(time.time()))
    signed = {"x-chiron-user": "ana@example.com", "x-chiron-name": "", "x-chiron-ts": ts,
              "x-chiron-sig": sign("s", "ana@example.com", "", ts)}
    assert client.post("/api/preferencias", json={"acento": "rosa"}, headers=signed).status_code == 200
    assert client.get("/api/preferencias", headers=signed).json() == {"acento": "rosa"}


def test_schema_adds_the_column_idempotently():
    assert "ADD COLUMN IF NOT EXISTS acento TEXT NOT NULL DEFAULT 'menta'" in db.SCHEMA
