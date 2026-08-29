"""Integração pequena e direta com o Google Calendar."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarService:
    def __init__(self, token_path: str | None = None, timezone: str | None = None) -> None:
        self.token_path = Path(token_path or os.getenv("TOKEN_PATH", "data/token.json"))
        self.timezone = timezone or os.getenv("CALENDAR_TIMEZONE", "America/Sao_Paulo")

    @staticmethod
    def _client_config() -> dict[str, Any]:
        return {
            "web": {
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [os.environ["GOOGLE_REDIRECT_URI"]],
            }
        }

    def authorization_url(self) -> tuple[str, str]:
        flow = Flow.from_client_config(self._client_config(), scopes=SCOPES)
        flow.redirect_uri = os.environ["GOOGLE_REDIRECT_URI"]
        return flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")

    def save_authorization_code(self, code: str, state: str) -> None:
        flow = Flow.from_client_config(self._client_config(), scopes=SCOPES, state=state)
        flow.redirect_uri = os.environ["GOOGLE_REDIRECT_URI"]
        flow.fetch_token(code=code)
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(flow.credentials.to_json(), encoding="utf-8")
        self.token_path.chmod(0o600)

    def _credentials(self) -> Credentials:
        if not self.token_path.exists():
            raise RuntimeError("Google Calendar não está conectado. Use o botão para conectar sua conta.")
        credentials = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self.token_path.write_text(credentials.to_json(), encoding="utf-8")
            self.token_path.chmod(0o600)
        if not credentials.valid:
            raise RuntimeError("A autorização do Google expirou. Conecte sua conta novamente.")
        return credentials

    def is_connected(self) -> bool:
        try:
            self._credentials()
            return True
        except (RuntimeError, ValueError, KeyError):
            return False

    def _api(self):
        return build("calendar", "v3", credentials=self._credentials(), cache_discovery=False)

    @staticmethod
    def _event_data(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": event["id"],
            "title": event.get("summary", "Sem título"),
            "start": event.get("start", {}).get("dateTime", event.get("start", {}).get("date")),
            "end": event.get("end", {}).get("dateTime", event.get("end", {}).get("date")),
            "description": event.get("description"),
            "location": event.get("location"),
            "html_link": event.get("htmlLink"),
        }

    def get_events(self, start_datetime: str, end_datetime: str) -> list[dict[str, Any]]:
        response = self._api().events().list(
            calendarId="primary", timeMin=start_datetime, timeMax=end_datetime,
            singleEvents=True, orderBy="startTime",
        ).execute()
        return [self._event_data(event) for event in response.get("items", [])]

    def get_event(self, event_id: str) -> dict[str, Any]:
        return self._event_data(self._api().events().get(calendarId="primary", eventId=event_id).execute())

    def create_event(self, title: str, start_datetime: str, end_datetime: str,
                     description: str | None = None, location: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "summary": title,
            "start": {"dateTime": start_datetime, "timeZone": self.timezone},
            "end": {"dateTime": end_datetime, "timeZone": self.timezone},
        }
        if description:
            body["description"] = description
        if location:
            body["location"] = location
        return self._event_data(self._api().events().insert(calendarId="primary", body=body).execute())

    def update_event(self, event_id: str, **changes: str | None) -> dict[str, Any]:
        current = self._api().events().get(calendarId="primary", eventId=event_id).execute()
        mapping = {"title": "summary", "description": "description", "location": "location"}
        for name, field in mapping.items():
            if changes.get(name) is not None:
                current[field] = changes[name]
        for name, field in (("start_datetime", "start"), ("end_datetime", "end")):
            if changes.get(name) is not None:
                current[field] = {"dateTime": changes[name], "timeZone": self.timezone}
        updated = self._api().events().update(calendarId="primary", eventId=event_id, body=current).execute()
        return self._event_data(updated)

    def delete_event(self, event_id: str) -> None:
        self._api().events().delete(calendarId="primary", eventId=event_id).execute()
