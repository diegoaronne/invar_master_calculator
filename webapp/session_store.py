"""Almacén de estados de sesión en memoria, aislado por sesión.

Diseño pensado para migrar luego a multitenant: la interfaz (get/put/reset)
se mantiene igual aunque el backend cambie de un dict en memoria a una DB.
Por ahora, cada sesión = una copia independiente del proyecto (típicamente
el proyecto demo), para que varias personas puedan probar el prototipo al
mismo tiempo sin pisarse los datos.
"""
from __future__ import annotations

import copy
import uuid
from typing import Dict, Optional

from .estado import EstadoSesion

_STORE: Dict[str, EstadoSesion] = {}


def new_session_id() -> str:
    return uuid.uuid4().hex


def get(session_id: str) -> Optional[EstadoSesion]:
    return _STORE.get(session_id)


def put(session_id: str, estado: EstadoSesion) -> None:
    _STORE[session_id] = estado


def reset(session_id: str, factory) -> EstadoSesion:
    """Reinicia la sesión con una copia fresca producida por `factory()`."""
    estado = factory()
    _STORE[session_id] = estado
    return estado


def clone_for_session(estado_base: EstadoSesion) -> EstadoSesion:
    """Copia profunda para que cada sesión tenga su propio proyecto aislado."""
    return copy.deepcopy(estado_base)


def drop(session_id: str) -> None:
    _STORE.pop(session_id, None)
