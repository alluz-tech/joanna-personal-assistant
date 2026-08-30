"""Transcrição (áudio → texto) e síntese (texto → áudio) via OpenAI.

Mantém a conversa por voz reaproveitando o mesmo agente da conversa por texto:
o áudio vira texto, passa pelo agente e a resposta é falada de volta.
"""
from __future__ import annotations

import io
import os
import re
from typing import Any

from openai import OpenAI

TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "shimmer")

_MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

# "31/08", "31/08/2026" — evita casar dentro de números maiores ou frações.
_DATE_RE = re.compile(r"(?<!\d)(?P<d>[0-3]?\d)/(?P<m>[01]?\d)(?:/(?P<y>\d{2,4}))?(?![/\d])")
# "14h", "14h30", "9:05" — o TTS lê "h" e ":" como texto ("quatorze agá trinta").
# O "-" no lookbehind evita mexer em offsets ISO ("...T14:00:00-03:00").
_TIME_RE = re.compile(r"(?<![:\w-])(?P<h>[0-2]?\d)(?:[:h](?P<min>[0-5]\d)|h)(?!\w)")


def _say_date(match: re.Match) -> str:
    day, month = int(match["d"]), int(match["m"])
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return match[0]
    # "2/3" costuma ser fração; só tratamos como data se algo a marca como tal
    # (dia ou mês com dois dígitos, ou ano presente).
    if len(match["d"]) < 2 and len(match["m"]) < 2 and not match["y"]:
        return match[0]
    spoken = f"{day} de {_MONTHS[month - 1]}"
    if match["y"]:
        year = int(match["y"])
        spoken += f" de {year + 2000 if year < 100 else year}"
    return spoken


def _say_time(match: re.Match) -> str:
    hour = int(match["h"])
    minute = int(match["min"]) if match["min"] else 0
    if hour > 24 or minute > 59:
        return match[0]
    unit = "hora" if hour == 1 else "horas"
    return f"{hour} {unit} e {minute}" if minute else f"{hour} {unit}"


def speakable(text: str) -> str:
    """Expande datas e horários abreviados para o TTS não soletrar a pontuação."""
    text = _DATE_RE.sub(_say_date, text)
    text = _TIME_RE.sub(_say_time, text)
    return text


class VoiceService:
    def __init__(self, client: Any | None = None) -> None:
        self.client = client or OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def transcribe(self, audio: bytes, filename: str = "audio.webm") -> str:
        buffer = io.BytesIO(audio)
        buffer.name = filename or "audio.webm"
        result = self.client.audio.transcriptions.create(
            model=TRANSCRIBE_MODEL, file=buffer, language="pt"
        )
        return (getattr(result, "text", "") or "").strip()

    def synthesize(self, text: str) -> bytes:
        response = self.client.audio.speech.create(
            model=TTS_MODEL, voice=TTS_VOICE, input=speakable(text), response_format="mp3"
        )
        return response.read()
