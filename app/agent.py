"""Agente OpenAI com somente as ferramentas necessárias ao MVP."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from openai import OpenAI

from app.calendar_service import CalendarService

TOOLS = [
    {"type": "function", "name": "get_events", "description": "Lista eventos em um intervalo ISO 8601.", "parameters": {"type": "object", "properties": {"start_datetime": {"type": "string"}, "end_datetime": {"type": "string"}}, "required": ["start_datetime", "end_datetime"], "additionalProperties": False}},
    {"type": "function", "name": "get_event", "description": "Busca um evento pelo id.", "parameters": {"type": "object", "properties": {"event_id": {"type": "string"}}, "required": ["event_id"], "additionalProperties": False}},
    {"type": "function", "name": "create_event", "description": "Cria um evento quando título, início e fim estiverem claros.", "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "start_datetime": {"type": "string"}, "end_datetime": {"type": "string"}, "description": {"type": "string"}, "location": {"type": "string"}, "attendees": {"type": "array", "items": {"type": "string"}, "description": "E-mails dos participantes."}}, "required": ["title", "start_datetime", "end_datetime"], "additionalProperties": False}},
    {"type": "function", "name": "update_event", "description": "Atualiza um evento identificado por id.", "parameters": {"type": "object", "properties": {"event_id": {"type": "string"}, "title": {"type": "string"}, "start_datetime": {"type": "string"}, "end_datetime": {"type": "string"}, "description": {"type": "string"}, "location": {"type": "string"}, "attendees": {"type": "array", "items": {"type": "string"}, "description": "Lista completa de e-mails dos participantes."}}, "required": ["event_id"], "additionalProperties": False}},
    {"type": "function", "name": "delete_event", "description": "Solicita a exclusão de um evento; a aplicação exigirá confirmação explícita do usuário.", "parameters": {"type": "object", "properties": {"event_id": {"type": "string"}}, "required": ["event_id"], "additionalProperties": False}},
]


def _format_event(event: dict[str, Any]) -> str:
    return f"{event['title']} — {event['start']} até {event['end']}"


class CalendarAgent:
    def __init__(self, calendar: CalendarService, client: Any | None = None) -> None:
        self.calendar = calendar
        self.client = client or OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.timezone = calendar.timezone

    def _instructions(self) -> str:
        now = datetime.now(ZoneInfo(self.timezone)).isoformat()
        return f"""Você é uma secretária digital em português brasileiro. Hoje é {now} no fuso {self.timezone}.
Use ferramentas para qualquer informação do calendário; não invente eventos. Datas devem ser ISO 8601 com offset de {self.timezone}. Organize consultas cronologicamente e responda de modo breve. Para criar, peça uma informação essencial ausente (título, data ou horário). Quando o usuário não informar horário final, crie um evento de uma hora e informe isso na confirmação. Nunca alegue que excluiu ou alterou um evento sem chamar a ferramenta. A ferramenta delete_event apenas solicita confirmação: apresente o evento encontrado e pergunte se a pessoa confirma."""

    def _call_tool(self, name: str, args: dict[str, Any], pending: dict[str, Any]) -> dict[str, Any]:
        if name == "delete_event":
            event = self.calendar.get_event(args["event_id"])
            pending["delete_event"] = event
            return {"status": "confirmation_required", "event": event, "message": f"Confirma excluir {_format_event(event)}?"}
        if name == "get_events":
            return {"events": self.calendar.get_events(**args)}
        if name == "get_event":
            return self.calendar.get_event(**args)
        if name == "create_event":
            return self.calendar.create_event(**args)
        if name == "update_event":
            return self.calendar.update_event(**args)
        raise ValueError(f"Ferramenta desconhecida: {name}")

    def chat(self, message: str, pending: dict[str, Any]) -> str:
        response = self.client.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), instructions=self._instructions(), input=message, tools=TOOLS)
        while True:
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                return response.output_text
            outputs = []
            for call in calls:
                try:
                    result = self._call_tool(call.name, json.loads(call.arguments), pending)
                except Exception as exc:  # A API deve transformar falhas externas em uma resposta útil.
                    result = {"error": str(exc)}
                outputs.append({"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result, ensure_ascii=False)})
            response = self.client.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), instructions=self._instructions(), previous_response_id=response.id, input=outputs, tools=TOOLS)
