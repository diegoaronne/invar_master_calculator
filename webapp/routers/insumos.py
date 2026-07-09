"""Explosión de insumos y programa de suministros (videos 22 y 28).

Páginas HTML:
    GET /insumos                vista de trabajo con panel de configuración

API JSON:
    GET /api/insumos            explosión (y suministros) parametrizada:
        nivel      basicos | compuestos | primer
        tipos      lista separada por comas de TipoRecurso (vacío = todos)
        desglosar  1 = abrir el costo horario del equipo en sus cargos
        programa   1 = anexar el programa de suministros por periodo
        escala     Días | Semanas | Quincenas | Meses
        por        cantidad | monto
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from invar_calculator.modelos import TipoRecurso
from invar_calculator.programa import EscalaTiempo

from .. import serializar, session_store
from ..estado import EstadoSesion

router = APIRouter()
templates = Jinja2Templates(directory="webapp/templates")


def _estado(request: Request) -> Optional[EstadoSesion]:
    session_id = request.cookies.get("session_id")
    return session_store.get(session_id) if session_id else None


@router.get("/insumos", response_class=HTMLResponse)
def insumos(request: Request):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/")
    proyecto = estado.proyecto
    return templates.TemplateResponse(request, "insumos.html", {
        "nombre_proyecto": proyecto.nombre,
        "tipos": [t.value for t in serializar.ORDEN_TIPOS],
        "escalas": [e.value for e in EscalaTiempo],
        "hay_programa": bool(proyecto.programa.actividades),
    })


@router.get("/api/insumos")
def api_insumos(request: Request,
                nivel: str = "basicos",
                tipos: str = "",
                desglosar: int = 0,
                programa: int = 0,
                escala: str = EscalaTiempo.MES.value,
                por: str = "monto"):
    estado = _estado(request)
    if estado is None:
        return JSONResponse(
            {"ok": False, "error": "Sesión expirada; vuelve a iniciar sesión."},
            status_code=401)
    try:
        conjunto = None
        if tipos.strip():
            conjunto = {TipoRecurso(t.strip())
                        for t in tipos.split(",") if t.strip()}
        if por not in ("cantidad", "monto"):
            raise ValueError("El parámetro 'por' debe ser 'cantidad' o 'monto'.")
        datos = serializar.datos_insumos(
            estado.proyecto,
            nivel=nivel,
            tipos=conjunto,
            desglosar_equipo=bool(desglosar),
            con_programa=bool(programa),
            escala=EscalaTiempo(escala),
            por=por)
    except (ValueError, ArithmeticError, KeyError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return {"ok": True, "insumos": datos}
