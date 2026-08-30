"""Transcrição (áudio → texto) e síntese (texto → áudio) via OpenAI.

Mantém a conversa por voz reaproveitando o mesmo agente da conversa por texto:
o áudio vira texto, passa pelo agente e a resposta é falada de volta.
"""
from __future__ import annotations

import io
import os
from typing import Any

from openai import OpenAI

TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "shimmer")


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
            model=TTS_MODEL, voice=TTS_VOICE, input=text, response_format="mp3"
        )
        return response.read()
