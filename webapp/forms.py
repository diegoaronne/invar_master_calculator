"""Helpers para convertir campos de formulario HTML a los tipos que
espera el motor (que acepta strings decimales/fórmulas de forma nativa)."""
from __future__ import annotations

import datetime as dt
from typing import Optional
from urllib.parse import quote

from fastapi.responses import RedirectResponse


def texto(valor: Optional[str], default: str = "") -> str:
    return (valor or "").strip() or default


def numero(valor: Optional[str], default: str = "0") -> str:
    """El motor acepta strings ("14.5", "1/10"); solo normalizamos vacíos."""
    limpio = (valor or "").strip().replace(",", "")
    return limpio or default


def numero_opcional(valor: Optional[str]) -> Optional[str]:
    limpio = (valor or "").strip().replace(",", "")
    return limpio or None


def entero(valor: Optional[str], default: int = 0) -> int:
    limpio = (valor or "").strip()
    return int(limpio) if limpio else default


def fecha(valor: Optional[str]) -> Optional[dt.date]:
    limpio = (valor or "").strip()
    return dt.date.fromisoformat(limpio) if limpio else None


def marcado(valor: Optional[str]) -> bool:
    return valor is not None


def redirigir(url: str, error: str | None = None,
              ok: str | None = None) -> RedirectResponse:
    if error:
        url = f"{url}?error={quote(error)}"
    elif ok:
        url = f"{url}?ok={quote(ok)}"
    return RedirectResponse(url=url, status_code=303)
