from app.calendar_service import CalendarService
import app.calendar_service as calendar_service


def test_get_events_returns_normalized_calendar_items(monkeypatch):
    class Request:
        def execute(self):
            return {"items": [{
                "id": "abc", "summary": "Dentista",
                "start": {"dateTime": "2026-09-01T10:00:00-03:00"},
                "end": {"dateTime": "2026-09-01T11:00:00-03:00"},
                "location": "Clínica",
                "attendees": [
                    {"email": "ana@ex.com", "displayName": "Ana", "responseStatus": "accepted", "organizer": True},
                    {"email": "sem-status@ex.com"},
                ],
            }]}
    class Events:
        def list(self, **kwargs):
            assert kwargs["orderBy"] == "startTime"
            return Request()
    class API:
        def events(self): return Events()
    service = CalendarService()
    monkeypatch.setattr(service, "_api", lambda: API())
    events = service.get_events("2026-09-01T00:00:00-03:00", "2026-09-02T00:00:00-03:00")
    assert events == [{
        "id": "abc", "title": "Dentista",
        "start": "2026-09-01T10:00:00-03:00", "end": "2026-09-01T11:00:00-03:00",
        "all_day": False, "description": None, "location": "Clínica", "html_link": None,
        "attendees": [
            {"email": "ana@ex.com", "name": "Ana", "status": "accepted", "organizer": True, "optional": False},
            {"email": "sem-status@ex.com", "name": "sem-status@ex.com", "status": "needsAction", "organizer": False, "optional": False},
        ],
    }]


def test_get_events_marks_all_day_events(monkeypatch):
    class Request:
        def execute(self):
            return {"items": [{"id": "d1", "summary": "Feriado", "start": {"date": "2026-09-07"}, "end": {"date": "2026-09-08"}}]}
    class Events:
        def list(self, **kwargs): return Request()
    class API:
        def events(self): return Events()
    service = CalendarService()
    monkeypatch.setattr(service, "_api", lambda: API())
    (event,) = service.get_events("2026-09-01T00:00:00-03:00", "2026-09-30T00:00:00-03:00")
    assert event["all_day"] is True
    assert event["start"] == "2026-09-07"
    assert event["attendees"] == []


def test_get_events_passes_query_when_provided(monkeypatch):
    seen = {}
    class Request:
        def execute(self): return {"items": []}
    class Events:
        def list(self, **kwargs): seen.update(kwargs); return Request()
    class API:
        def events(self): return Events()
    service = CalendarService()
    monkeypatch.setattr(service, "_api", lambda: API())
    service.get_events("2026-09-01T00:00:00-03:00", "2026-09-02T00:00:00-03:00", "dentista")
    assert seen["q"] == "dentista"


def test_create_event_uses_configured_timezone(monkeypatch):
    captured = {}
    class Request:
        def execute(self): return {"id": "new", "summary": "João", "start": {"dateTime": "2026-09-01T14:00:00-03:00"}, "end": {"dateTime": "2026-09-01T15:00:00-03:00"}}
    class Events:
        def insert(self, **kwargs): captured.update(kwargs); return Request()
    class API:
        def events(self): return Events()
    service = CalendarService(timezone="America/Sao_Paulo")
    monkeypatch.setattr(service, "_api", lambda: API())
    service.create_event("João", "2026-09-01T14:00:00-03:00", "2026-09-01T15:00:00-03:00")
    assert captured["body"]["start"]["timeZone"] == "America/Sao_Paulo"


def test_create_event_includes_attendees(monkeypatch):
    captured = {}
    class Request:
        def execute(self): return {"id": "n", "summary": "Reunião", "start": {"dateTime": "x"}, "end": {"dateTime": "y"}}
    class Events:
        def insert(self, **kwargs): captured.update(kwargs); return Request()
    class API:
        def events(self): return Events()
    service = CalendarService()
    monkeypatch.setattr(service, "_api", lambda: API())
    service.create_event("Reunião", "s", "e", attendees=["ana@ex.com", "bob@ex.com"])
    assert captured["body"]["attendees"] == [{"email": "ana@ex.com"}, {"email": "bob@ex.com"}]


def test_update_event_replaces_attendees(monkeypatch):
    captured = {}
    class GetRequest:
        def execute(self): return {"id": "e", "summary": "Antiga", "attendees": [{"email": "old@ex.com"}]}
    class UpdateRequest:
        def execute(self): return {"id": "e", "summary": "Antiga", "start": {"dateTime": "s"}, "end": {"dateTime": "x"}}
    class Events:
        def get(self, **kwargs): return GetRequest()
        def update(self, **kwargs): captured.update(kwargs); return UpdateRequest()
    class API:
        def events(self): return Events()
    service = CalendarService()
    monkeypatch.setattr(service, "_api", lambda: API())
    service.update_event("e", attendees=["new@ex.com"])
    assert captured["body"]["attendees"] == [{"email": "new@ex.com"}]


def test_oauth_preserves_pkce_verifier_between_authorization_steps(monkeypatch, tmp_path):
    created = []

    class Flow:
        code_verifier = "pkce-verifier"

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.credentials = type("Credentials", (), {"to_json": lambda self: "{}"})()

        @classmethod
        def from_client_config(cls, _config, scopes, **kwargs):
            flow = cls(**kwargs)
            created.append(flow)
            return flow

        def authorization_url(self, **_kwargs):
            return "https://accounts.google.com/example", "oauth-state"

        def fetch_token(self, **kwargs):
            self.token_code = kwargs["code"]

    monkeypatch.setattr(calendar_service, "Flow", Flow)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:5089/auth/google/callback")
    service = CalendarService(token_path=str(tmp_path / "token.json"))

    _, state = service.authorization_url()
    service.save_authorization_code("authorization-code", state)

    assert created[1].kwargs["code_verifier"] == "pkce-verifier"
    assert created[1].token_code == "authorization-code"
