from types import SimpleNamespace

from app.agent import CalendarAgent


class Calendar:
    timezone = "America/Sao_Paulo"
    def get_events(self, **kwargs): return [{"id": "1", "title": "Reunião", "start": kwargs["start_datetime"], "end": kwargs["end_datetime"]}]
    def get_event(self, event_id): return {"id": event_id, "title": "Reunião", "start": "2026-09-01T15:00:00-03:00", "end": "2026-09-01T16:00:00-03:00"}


def test_agent_interprets_simple_query_with_tool_call():
    call = SimpleNamespace(type="function_call", name="get_events", arguments='{"start_datetime":"2026-09-01T00:00:00-03:00","end_datetime":"2026-09-02T00:00:00-03:00"}', call_id="call_1")
    first = SimpleNamespace(output=[call], id="r1", output_text="")
    second = SimpleNamespace(output=[], id="r2", output_text="Você tem uma reunião.")
    class Responses:
        def __init__(self): self.calls = []
        def create(self, **kwargs): self.calls.append(kwargs); return first if len(self.calls) == 1 else second
    responses = Responses()
    agent = CalendarAgent(Calendar(), client=SimpleNamespace(responses=responses))
    assert agent.chat("O que eu tenho amanhã?", {}) == "Você tem uma reunião."
    assert '"events"' in responses.calls[1]["input"][0]["output"]


def test_delete_requires_confirmation_before_execution():
    pending = {}
    agent = CalendarAgent(Calendar(), client=SimpleNamespace())
    result = agent._call_tool("delete_event", {"event_id": "event-1"}, pending)
    assert result["status"] == "confirmation_required"
    assert pending["delete_event"]["id"] == "event-1"
