import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.app)


class FakeCalendar:
    timezone = "America/Sao_Paulo"

    def __init__(self):
        self.created = None
        self.updated = None
        self.deleted = None

    def is_connected(self):
        return True

    def get_events(self, start, end, query=None):
        return [{"id": "1", "title": "Reunião", "start": start, "end": end, "attendees": [], "all_day": False}]

    def create_event(self, title, start, end, description=None, location=None, attendees=None):
        self.created = dict(title=title, start=start, end=end, description=description, location=location, attendees=attendees)
        return {"id": "new", "title": title, "start": start, "end": end}

    def update_event(self, event_id, **changes):
        self.updated = (event_id, changes)
        return {"id": event_id, "title": changes.get("title", "Reunião")}

    def delete_event(self, event_id):
        self.deleted = event_id


def use_fake(monkeypatch):
    fake = FakeCalendar()
    monkeypatch.setattr(main, "calendar", fake)
    return fake


def test_list_events_returns_payload(monkeypatch):
    use_fake(monkeypatch)
    res = client.get("/api/events", params={"start": "2026-09-01T00:00:00-03:00", "end": "2026-09-02T00:00:00-03:00"})
    assert res.status_code == 200
    assert res.json()["events"][0]["title"] == "Reunião"


def test_list_events_requires_connection(monkeypatch):
    fake = use_fake(monkeypatch)
    monkeypatch.setattr(fake, "is_connected", lambda: False)
    res = client.get("/api/events", params={"start": "a", "end": "b"})
    assert res.status_code == 400


def test_create_event_passes_attendees(monkeypatch):
    fake = use_fake(monkeypatch)
    res = client.post("/api/events", json={
        "title": "Call", "start": "2026-09-01T14:00:00-03:00", "end": "2026-09-01T15:00:00-03:00",
        "attendees": ["ana@ex.com"],
    })
    assert res.status_code == 201
    assert fake.created["attendees"] == ["ana@ex.com"]


def test_patch_event_only_sends_provided_fields(monkeypatch):
    fake = use_fake(monkeypatch)
    res = client.patch("/api/events/evt-1", json={"title": "Novo título"})
    assert res.status_code == 200
    event_id, changes = fake.updated
    assert event_id == "evt-1"
    assert changes == {"title": "Novo título"}


def test_delete_event(monkeypatch):
    fake = use_fake(monkeypatch)
    res = client.delete("/api/events/evt-9")
    assert res.status_code == 204
    assert fake.deleted == "evt-9"
