from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from app.agent import CalendarAgent
from app.calendar_service import CalendarService

app = FastAPI(title="Joanna — Assistente de Agenda")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
calendar = CalendarService()
agent = CalendarAgent(calendar)
oauth_states: set[str] = set()
pending_actions: dict[str, dict] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str


class EventPayload(BaseModel):
    title: str
    start: str
    end: str
    description: str | None = None
    location: str | None = None
    attendees: list[str] = []


class EventPatch(BaseModel):
    title: str | None = None
    start: str | None = None
    end: str | None = None
    description: str | None = None
    location: str | None = None
    attendees: list[str] | None = None


def require_connected() -> None:
    if not calendar.is_connected():
        raise HTTPException(400, "Conecte seu Google Calendar antes de usar a agenda.")


def is_confirmation(text: str) -> bool:
    return text.strip().lower() in {"sim", "s", "confirmo", "pode excluir", "pode apagar", "confirmar"}


def is_rejection(text: str) -> bool:
    return text.strip().lower() in {"não", "nao", "n", "cancele", "cancelar"}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/auth-status")
def auth_status():
    return {"connected": calendar.is_connected()}


@app.get("/api/config")
def config():
    return {"timezone": calendar.timezone, "connected": calendar.is_connected()}


@app.get("/api/events")
def list_events(start: str, end: str, q: str | None = None):
    require_connected()
    try:
        return {"events": calendar.get_events(start, end, q)}
    except Exception as exc:
        raise HTTPException(502, f"Não consegui carregar os eventos: {exc}") from exc


@app.post("/api/events", status_code=201)
def add_event(body: EventPayload):
    require_connected()
    try:
        return calendar.create_event(
            body.title, body.start, body.end, body.description, body.location, body.attendees or None
        )
    except Exception as exc:
        raise HTTPException(502, f"Não consegui criar o evento: {exc}") from exc


@app.patch("/api/events/{event_id}")
def edit_event(event_id: str, body: EventPatch):
    require_connected()
    changes = {
        "title": body.title,
        "description": body.description,
        "location": body.location,
        "start_datetime": body.start,
        "end_datetime": body.end,
        "attendees": body.attendees,
    }
    changes = {key: value for key, value in changes.items() if value is not None}
    try:
        return calendar.update_event(event_id, **changes)
    except Exception as exc:
        raise HTTPException(502, f"Não consegui atualizar o evento: {exc}") from exc


@app.delete("/api/events/{event_id}", status_code=204)
def remove_event(event_id: str):
    require_connected()
    try:
        calendar.delete_event(event_id)
    except Exception as exc:
        raise HTTPException(502, f"Não consegui excluir o evento: {exc}") from exc


@app.get("/auth/google")
def google_login():
    try:
        url, state = calendar.authorization_url()
    except KeyError as exc:
        raise HTTPException(500, f"Variável de ambiente ausente: {exc.args[0]}") from exc
    oauth_states.add(state)
    return RedirectResponse(url)


@app.get("/auth/google/callback")
def google_callback(code: str, state: str):
    if state not in oauth_states:
        raise HTTPException(400, "Estado OAuth inválido.")
    oauth_states.remove(state)
    calendar.save_authorization_code(code, state)
    return RedirectResponse("/")


@app.post("/api/chat")
def chat(body: ChatRequest):
    if not calendar.is_connected():
        raise HTTPException(400, "Conecte seu Google Calendar antes de conversar com a assistente.")
    message = body.message.strip()
    if not message:
        raise HTTPException(422, "A mensagem não pode estar vazia.")
    pending = pending_actions.setdefault(body.session_id, {})
    event = pending.get("delete_event")
    if event and is_confirmation(message):
        calendar.delete_event(event["id"])
        pending.pop("delete_event", None)
        return {"reply": f"Pronto, excluí o evento '{event['title']}'."}
    if event and is_rejection(message):
        pending.pop("delete_event", None)
        return {"reply": "Tudo bem, mantive o evento."}
    try:
        return {"reply": agent.chat(message, pending)}
    except Exception as exc:
        raise HTTPException(502, f"Não consegui processar o pedido: {exc}") from exc
