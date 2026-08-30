import base64
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


class FakeVoice:
    def __init__(self):
        self.transcribed = None

    def transcribe(self, audio, filename="audio.webm"):
        self.transcribed = (audio, filename)
        return "O que eu tenho amanhã?"

    def synthesize(self, text):
        return b"ID3-fake-mp3"


def test_voice_transcribes_runs_agent_and_speaks(monkeypatch):
    use_fake(monkeypatch)
    monkeypatch.setattr(main, "voice", FakeVoice())
    monkeypatch.setattr(
        main.agent, "chat", lambda message, pending, prev=None: (f"Resposta para: {message}", "r1")
    )
    res = client.post(
        "/api/voice",
        data={"session_id": "s1"},
        files={"audio": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["transcript"] == "O que eu tenho amanhã?"
    assert body["reply"] == "Resposta para: O que eu tenho amanhã?"
    assert base64.b64decode(body["audio"]) == b"ID3-fake-mp3"


def test_chat_remembers_context_across_turns(monkeypatch):
    use_fake(monkeypatch)
    main.sessions.pop("mem-1", None)
    seen = []

    def fake_chat(message, pending, previous_response_id=None):
        seen.append(previous_response_id)
        return f"ok {len(seen)}", f"resp-{len(seen)}"

    monkeypatch.setattr(main.agent, "chat", fake_chat)
    client.post("/api/chat", json={"message": "oi", "session_id": "mem-1"})
    client.post("/api/chat", json={"message": "e depois?", "session_id": "mem-1"})
    assert seen == [None, "resp-1"]


def test_voice_requires_connection(monkeypatch):
    fake = use_fake(monkeypatch)
    monkeypatch.setattr(fake, "is_connected", lambda: False)
    res = client.post(
        "/api/voice",
        data={"session_id": "s1"},
        files={"audio": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 400


def test_voice_rejects_empty_transcript(monkeypatch):
    use_fake(monkeypatch)
    empty = FakeVoice()
    empty.transcribe = lambda audio, filename="audio.webm": ""
    monkeypatch.setattr(main, "voice", empty)
    res = client.post(
        "/api/voice",
        data={"session_id": "s1"},
        files={"audio": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 422
