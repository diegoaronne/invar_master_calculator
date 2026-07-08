"""Rutas de reportes: vista interna (todo) y vista cliente (filtrada),
APU por concepto, y descarga CSV de cualquier tabla visible.

La conversión Tabla→HTML y el filtrado cliente viven en render_html; el
motor de reportes (invar_calculator.reportes) no se modifica.
"""
from __future__ import annotations

from typing import List, Tuple

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

import invar_calculator as ic
from invar_calculator import reportes as motor_reportes

from .. import render_html, session_store
from ..estado import EstadoSesion

router = APIRouter()
templates = Jinja2Templates(directory="webapp/templates")

MODOS = ("interno", "cliente")


def _estado_o_error(request: Request) -> EstadoSesion:
    session_id = request.cookies.get("session_id")
    estado = session_store.get(session_id) if session_id else None
    if estado is None:
        raise HTTPException(status_code=440,
                            detail="Sesión expirada, inicia de nuevo.")
    return estado


def _salario_referencia_fsr(proyecto: ic.Proyecto) -> str | None:
    """Salario base representativo para el reporte FSR: el de la primera
    mano de obra simple del catálogo."""
    for recurso in proyecto.catalogo.por_tipo(ic.TipoRecurso.MANO_OBRA):
        if recurso.salario_base is not None and not recurso.componentes:
            return str(recurso.salario_base)
    return None


def _tabla_programa(proyecto: ic.Proyecto):
    """Programa de obra (cantidades por mes) construido en la capa web a
    partir de la distribución del motor."""
    datos = proyecto.programa.programa_cantidades(ic.EscalaTiempo.MES)
    periodos = sorted({p for series in datos.values() for p in series})
    tabla = motor_reportes.Tabla("Programa de obra (cantidades por mes)",
                                 ["Concepto"] + periodos + ["Total"])
    for clave, series in datos.items():
        valores = [proyecto.precision.factor(series.get(p, 0))
                   for p in periodos]
        total = proyecto.precision.factor(
            sum(series.values(), start=ic.D(0)))
        tabla.agregar_fila(clave, *valores, total)
    return tabla


def _tablas_del_estado(estado: EstadoSesion, modo: str) -> List:
    """Reúne las Tablas de reporte para un modo dado, aplicando el
    filtrado de la vista cliente (tablas completas y filas sensibles)."""
    proyecto = estado.proyecto
    tablas: List = []

    presupuesto = motor_reportes.reporte_presupuesto(proyecto)
    if modo == "cliente":
        tablas.append(render_html.presupuesto_para_cliente(presupuesto))
    else:
        tablas.append(presupuesto)

    if proyecto.programa.actividades:
        tablas.append(_tabla_programa(proyecto))

    if modo == "interno":
        tablas.append(motor_reportes.reporte_pie_precios(proyecto))
        salario = _salario_referencia_fsr(proyecto)
        if salario is not None:
            tablas.append(motor_reportes.reporte_fsr(proyecto, salario))
        tablas.append(motor_reportes.reporte_explosion(proyecto))
        if proyecto.programa.actividades:
            tablas.append(motor_reportes.reporte_suministros(
                proyecto, ic.EscalaTiempo.MES))
        if estado.resultado_financiamiento is not None:
            tablas.append(motor_reportes.reporte_financiamiento(
                estado.resultado_financiamiento, "horizontal"))

    return tablas


def _tablas_apu(estado: EstadoSesion, modo: str) -> List[Tuple[str, object]]:
    """Pares (clave, tabla APU) por concepto, ya filtrados según el modo."""
    resultado = []
    for concepto in estado.proyecto.iter_conceptos():
        tabla = motor_reportes.reporte_apu(estado.proyecto, concepto)
        if modo == "cliente":
            tabla = render_html.apu_para_cliente(tabla)
        resultado.append((concepto.clave, tabla))
    return resultado


@router.get("/reportes/{modo}", response_class=HTMLResponse)
def ver_reportes(modo: str, request: Request):
    if modo not in MODOS:
        raise HTTPException(status_code=404)

    estado = _estado_o_error(request)
    tablas = _tablas_del_estado(estado, modo)
    solo_imprimibles = modo == "cliente"

    html_tablas = "".join(
        render_html.tabla_a_html(
            t, solo_imprimibles=solo_imprimibles,
            enlace_csv=f"/reportes/{modo}/csv/{i}")
        for i, t in enumerate(tablas))

    conceptos = [c.clave for c in estado.proyecto.iter_conceptos()]
    return templates.TemplateResponse(
        request,
        "reporte.html",
        {
            "modo": modo,
            "nombre_proyecto": estado.proyecto.nombre,
            "html_tablas": html_tablas,
            "conceptos": conceptos,
        },
    )


@router.get("/reportes/{modo}/apu/{clave}", response_class=HTMLResponse)
def ver_apu(modo: str, clave: str, request: Request):
    if modo not in MODOS:
        raise HTTPException(status_code=404)
    estado = _estado_o_error(request)
    for clave_apu, tabla in _tablas_apu(estado, modo):
        if clave_apu == clave:
            html_tablas = render_html.tabla_a_html(
                tabla, solo_imprimibles=(modo == "cliente"),
                enlace_csv=f"/reportes/{modo}/apu/{clave}/csv")
            return templates.TemplateResponse(
                request, "reporte.html",
                {
                    "modo": modo,
                    "nombre_proyecto": estado.proyecto.nombre,
                    "html_tablas": html_tablas,
                    "conceptos": [],
                })
    raise HTTPException(status_code=404, detail=f"Sin APU para {clave!r}.")


def _respuesta_csv(tabla, nombre: str, solo_imprimibles: bool):
    contenido = tabla.a_csv(solo_imprimibles=solo_imprimibles)
    return PlainTextResponse(
        contenido, media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="{nombre}.csv"'})


@router.get("/reportes/{modo}/csv/{indice}")
def descargar_csv(modo: str, indice: int, request: Request):
    if modo not in MODOS:
        raise HTTPException(status_code=404)
    estado = _estado_o_error(request)
    tablas = _tablas_del_estado(estado, modo)
    if not 0 <= indice < len(tablas):
        raise HTTPException(status_code=404)
    return _respuesta_csv(tablas[indice], f"reporte-{modo}-{indice}",
                          solo_imprimibles=(modo == "cliente"))


@router.get("/reportes/{modo}/apu/{clave}/csv")
def descargar_apu_csv(modo: str, clave: str, request: Request):
    if modo not in MODOS:
        raise HTTPException(status_code=404)
    estado = _estado_o_error(request)
    for clave_apu, tabla in _tablas_apu(estado, modo):
        if clave_apu == clave:
            return _respuesta_csv(tabla, f"apu-{clave}",
                                  solo_imprimibles=(modo == "cliente"))
    raise HTTPException(status_code=404)
