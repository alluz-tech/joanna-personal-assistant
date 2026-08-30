import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi.testclient import TestClient

import app.auth as auth
import app.main as main

client = TestClient(main.app)


@pytest.mark.real_pin
def test_token_roundtrip():
    token = auth.issue_token()
    assert auth.token_valid(token)
    assert not auth.token_valid(None)
    assert not auth.token_valid("garbage")
    assert not auth.token_valid(token + "x")


def test_check_pin():
    assert auth.check_pin(auth.PIN)
    assert auth.check_pin(f"  {auth.PIN}  ")
    assert not auth.check_pin("000000")
    assert not auth.check_pin(None)


def test_unlock_sets_cookie_with_correct_pin():
    res = client.post("/auth/unlock", json={"pin": auth.PIN})
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert auth.COOKIE_NAME in res.cookies


def test_unlock_rejects_wrong_pin():
    res = client.post("/auth/unlock", json={"pin": "111111"})
    assert res.status_code == 401
    assert auth.COOKIE_NAME not in res.cookies


@pytest.mark.real_pin
def test_api_blocked_without_pin():
    fresh = TestClient(main.app)
    res = fresh.get("/api/config")
    assert res.status_code == 401


@pytest.mark.real_pin
def test_api_allowed_after_unlock():
    fresh = TestClient(main.app)
    fresh.post("/auth/unlock", json={"pin": auth.PIN})
    res = fresh.get("/api/config")
    assert res.status_code == 200
