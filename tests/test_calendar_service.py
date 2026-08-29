from app.calendar_service import CalendarService


def test_get_events_returns_normalized_calendar_items(monkeypatch):
    class Request:
        def execute(self):
            return {"items": [{"id": "abc", "summary": "Dentista", "start": {"dateTime": "2026-09-01T10:00:00-03:00"}, "end": {"dateTime": "2026-09-01T11:00:00-03:00"}, "location": "Clínica"}]}
    class Events:
        def list(self, **kwargs):
            assert kwargs["orderBy"] == "startTime"
            return Request()
    class API:
        def events(self): return Events()
    service = CalendarService()
    monkeypatch.setattr(service, "_api", lambda: API())
    events = service.get_events("2026-09-01T00:00:00-03:00", "2026-09-02T00:00:00-03:00")
    assert events == [{"id": "abc", "title": "Dentista", "start": "2026-09-01T10:00:00-03:00", "end": "2026-09-01T11:00:00-03:00", "description": None, "location": "Clínica", "html_link": None}]


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
