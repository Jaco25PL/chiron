"""Backend identity checks (api/security.py) and per-consultation ownership (agents/graph.py)."""

import time

import pytest

from api.security import DEV_USER, MAX_SKEW_S, Unauthorized, sign, verify

SECRET = "test-secret"


def signed_headers(email="ana@example.com", name="Ana%20P%C3%A9rez", ts=None, secret=SECRET):
    ts = str(int(time.time()) if ts is None else ts)
    return {"x-chiron-user": email, "x-chiron-name": name, "x-chiron-ts": ts, "x-chiron-sig": sign(secret, email, name, ts)}


def test_valid_signature_returns_the_user():
    assert verify(signed_headers(), secret=SECRET) == {"email": "ana@example.com", "name": "Ana Pérez"}


def test_wrong_secret_is_rejected():
    with pytest.raises(Unauthorized, match="bad signature"):
        verify(signed_headers(secret="other"), secret=SECRET)


def test_tampered_email_is_rejected():
    h = signed_headers()
    h["x-chiron-user"] = "mallory@example.com"
    with pytest.raises(Unauthorized, match="bad signature"):
        verify(h, secret=SECRET)


def test_old_signature_is_rejected():
    with pytest.raises(Unauthorized, match="expired"):
        verify(signed_headers(ts=int(time.time()) - MAX_SKEW_S - 5), secret=SECRET)


def test_missing_headers_are_rejected():
    with pytest.raises(Unauthorized, match="missing"):
        verify({}, secret=SECRET)


def test_dev_mode_without_secret_accepts_requests():
    assert verify({}, secret="") == DEV_USER
    assert verify({"x-chiron-user": "bob@example.com"}, secret="")["email"] == "bob@example.com"


# --- ownership (in-memory graph, no LLM calls) ----------------------------------------

def test_only_the_owner_can_read_a_consultation():
    from agents.graph import get_session, new_session

    ana, bob = {"email": "ana@example.com", "name": "Ana"}, {"email": "bob@example.com", "name": "Bob"}
    sid = new_session("mpna-disnea-icc", ana)
    assert get_session(sid, ana)["case_id"] == "mpna-disnea-icc"
    with pytest.raises(PermissionError):
        get_session(sid, bob)


def test_unknown_consultation_raises_key_error():
    from agents.graph import get_session

    with pytest.raises(KeyError):
        get_session("does-not-exist", {"email": "ana@example.com"})


def test_api_rejects_unsigned_requests_when_secret_is_set(monkeypatch):
    monkeypatch.setenv("CHIRON_FAKE", "1")
    monkeypatch.setenv("CHIRON_BACKEND_SECRET", SECRET)
    from fastapi.testclient import TestClient

    import api.main as main

    client = TestClient(main.app)
    assert client.get("/api/cases").status_code == 401
    assert client.get("/api/cases", headers=signed_headers()).status_code == 200
    assert client.get("/api/health").status_code == 200  # health stays public
