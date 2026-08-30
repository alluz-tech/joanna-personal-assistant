import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app.voice import VoiceService, speakable


@pytest.mark.parametrize(
    "raw, spoken",
    [
        ("Agendei para 31/08.", "Agendei para 31 de agosto."),
        ("Reunião em 31/08/2026 confirmada", "Reunião em 31 de agosto de 2026 confirmada"),
        ("dia 5/01/26", "dia 5 de janeiro de 2026"),
        ("de 01/12 a 05/12", "de 1 de dezembro a 5 de dezembro"),
        ("às 14h", "às 14 horas"),
        ("das 9h às 10h30", "das 9 horas às 10 horas e 30"),
        ("começa 9:05", "começa 9 horas e 5"),
        ("reunião de 1h", "reunião de 1 hora"),
        ("aberto 24h por dia", "aberto 24 horas por dia"),
    ],
)
def test_speakable_expands_dates_and_times(raw, spoken):
    assert speakable(raw) == spoken


@pytest.mark.parametrize(
    "unchanged",
    [
        "data inválida 45/13 ignorada",
        "veja a página 112/113",
        "no ramal 1234 agora",
        "proporção 2/3 do dia",
        "ISO 2026-08-31T14:00:00-03:00 intacto",
    ],
)
def test_speakable_leaves_non_dates_alone(unchanged):
    assert speakable(unchanged) == unchanged


def test_synthesize_speaks_normalized_text():
    captured = {}

    class FakeSpeech:
        def create(self, **kwargs):
            captured.update(kwargs)
            return type("R", (), {"read": staticmethod(lambda: b"mp3")})()

    class FakeClient:
        audio = type("A", (), {"speech": FakeSpeech()})()

    out = VoiceService(client=FakeClient()).synthesize("Marquei 31/08 às 14h.")
    assert out == b"mp3"
    assert captured["input"] == "Marquei 31 de agosto às 14 horas."
