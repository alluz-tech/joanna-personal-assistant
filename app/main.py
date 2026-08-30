from __future__ import annotations

import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from app import auth
from app.agent import CalendarAgent
from app.calendar_service import CalendarService
from app.voice import VoiceService

app = FastAPI(title="Joanna — Assistente de Agenda")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.middleware("http")
async def pin_gate(request: Request, call_next):
    """Exige o PIN nas rotas de dados; o restante (tela de acesso, estáticos) é livre."""
    path = request.url.path
    if path.startswith("/api") or path.startswith("/auth/google"):
        if not auth.token_valid(request.cookies.get(auth.COOKIE_NAME)):
            return JSONResponse({"detail": "Acesso bloqueado. Digite o código."}, status_code=401)
    return await call_next(request)


calendar = CalendarService()
agent = CalendarAgent(calendar)
voice = VoiceService()
oauth_states: set[str] = set()
# Estado por sessão de conversa: {"pending": {...}, "response_id": "..."}.
# "response_id" encadeia os turnos para a assistente lembrar do contexto.
sessions: dict[str, dict] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str


class UnlockRequest(BaseModel):
    pin: str


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


@app.post("/auth/unlock")
def unlock(body: UnlockRequest):
    if not auth.check_pin(body.pin):
        raise HTTPException(401, "Código incorreto.")
    response = JSONResponse({"ok": True})
    response.set_cookie(
        auth.COOKIE_NAME,
        auth.issue_token(),
        max_age=auth.MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


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


def handle_message(raw_message: str, session_id: str) -> str:
    """Fluxo de conversa compartilhado pelas rotas de texto e de voz."""
    if not calendar.is_connected():
        raise HTTPException(400, "Conecte seu Google Calendar antes de conversar com a assistente.")
    message = raw_message.strip()
    if not message:
        raise HTTPException(422, "A mensagem não pode estar vazia.")
    state = sessions.setdefault(session_id, {})
    pending = state.setdefault("pending", {})
    event = pending.get("delete_event")
    if event and is_confirmation(message):
        calendar.delete_event(event["id"])
        pending.pop("delete_event", None)
        return f"Pronto, excluí o evento '{event['title']}'."
    if event and is_rejection(message):
        pending.pop("delete_event", None)
        return "Tudo bem, mantive o evento."
    try:
        reply, response_id = agent.chat(message, pending, state.get("response_id"))
    except Exception as exc:
        raise HTTPException(502, f"Não consegui processar o pedido: {exc}") from exc
    state["response_id"] = response_id
    return reply


@app.post("/api/chat")
def chat(body: ChatRequest):
    return {"reply": handle_message(body.message, body.session_id)}


@app.post("/api/voice")
async def voice_chat(session_id: str = Form(...), audio: UploadFile = File(...)):
    if not calendar.is_connected():
        raise HTTPException(400, "Conecte seu Google Calendar antes de conversar com a assistente.")
    raw = await audio.read()
    if not raw:
        raise HTTPException(422, "Áudio vazio.")
    try:
        transcript = voice.transcribe(raw, audio.filename or "audio.webm")
    except Exception as exc:
        raise HTTPException(502, f"Não consegui transcrever o áudio: {exc}") from exc
    if not transcript:
        raise HTTPException(422, "Não entendi o áudio. Pode repetir?")
    reply = handle_message(transcript, session_id)
    audio_b64: str | None = None
    try:
        audio_b64 = base64.b64encode(voice.synthesize(reply)).decode("ascii")
    except Exception:
        audio_b64 = None  # se a síntese falhar, ainda devolvemos o texto
    return {"transcript": transcript, "reply": reply, "audio": audio_b64}
