"""Trava de acesso pessoal por PIN numérico.

Uso pessoal e local: um único código libera as rotas de dados. O código fica
em `JOANNA_PIN` (padrão `278395`). A liberação é um token assinado guardado num
cookie de sessão; o segredo é sorteado a cada reinício do servidor, então
reiniciar (ou fechar o navegador) obriga a digitar o PIN de novo.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

PIN = os.getenv("JOANNA_PIN", "278395")
COOKIE_NAME = "joanna_auth"
MAX_AGE = 60 * 60 * 12  # o token expira no servidor após 12h

_SECRET = secrets.token_bytes(32)  # sorteado a cada início do processo


def check_pin(pin: str | None) -> bool:
    return hmac.compare_digest((pin or "").strip(), PIN)


def issue_token() -> str:
    issued = str(int(time.time()))
    signature = hmac.new(_SECRET, issued.encode(), hashlib.sha256).hexdigest()
    return f"{issued}.{signature}"


def token_valid(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    issued, signature = token.split(".", 1)
    expected = hmac.new(_SECRET, issued.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        return time.time() - int(issued) < MAX_AGE
    except ValueError:
        return False
