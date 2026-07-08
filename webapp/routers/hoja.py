"""Hoja de Presupuesto (tree-grid), Ficha de Costeo y Gantt — la vista de
trabajo estilo OPUS.

Páginas HTML:
    GET  /hoja                  tree-grid jerárquico + Gantt con splitter
    GET  /matriz/{clave}        ficha de costeo de la matriz (APU abierto)
    GET  /pie                   configuración del pie de precios
    POST /pie/...               acciones del pie (modo, alta/baja de cargos)
    POST /hoja/capitulo|concepto  alta rápida desde la hoja

API JSON (edición en celda — el cliente hace fetch y actualiza celdas):
    GET    /api/hoja
    GET    /api/gantt
    GET    /api/matriz/{clave}
    PATCH  /api/concepto/{clave}          {cantidad|descripcion}
    PATCH  /api/agrupador                 {ruta, descripcion}
    PATCH  /api/matriz/{m}/insumo/{r}     {cantidad}
    POST   /api/matriz/{m}/insumo         {recurso, cantidad}
    DELETE /api/matriz/{m}/insumo/{r}
    PATCH  /api/recurso/{clave}           {costo|descripcion}
    PATCH  /api/pie/{identificador}       {porcentaje|base|formula}

Toda mutación devuelve el payload completo de la vista afectada para que
el cliente repinte valores sin recargar (y sin perder el foco de teclado).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import invar_calculator as ic
from invar_calculator.modelos import UNIDADES_PREDEFINIDAS

from .. import forms, serializar, session_store
from ..estado import EstadoSesion

router = APIRouter()
templates = Jinja2Templates(directory="webapp/templates")

ERRORES_MOTOR = (ValueError, ArithmeticError, KeyError)


def _estado(request: Request) -> Optional[EstadoSesion]:
    session_id = request.cookies.get("session_id")
    return session_store.get(session_id) if session_id else None


def _error(mensaje: str, codigo: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": mensaje}, status_code=codigo)


def _sin_sesion() -> JSONResponse:
    return _error("Sesión expirada; vuelve a iniciar sesión.", 401)


def _matriz(proyecto: ic.Proyecto, clave: str) -> ic.Matriz:
    recurso = proyecto.catalogo.obtener(clave)
    if not isinstance(recurso, ic.Matriz):
        raise ValueError(f"El recurso {clave!r} no es una matriz.")
    return recurso


def _concepto(proyecto: ic.Proyecto, clave: str) -> ic.Concepto:
    for concepto in proyecto.iter_conceptos():
        if concepto.clave == clave:
            return concepto
    raise KeyError(f"No existe el concepto {clave!r}.")


def _agrupador(raiz: ic.Agrupador, ruta: str) -> ic.Agrupador:
    nodo = raiz
    for tramo in [t for t in ruta.split("/") if t]:
        for hijo in nodo.hijos:
            if isinstance(hijo, ic.Agrupador) and hijo.clave == tramo:
                nodo = hijo
                break
        else:
            raise KeyError(f"No existe el agrupador {ruta!r}.")
    return nodo


# ================================================================ páginas
@router.get("/hoja", response_class=HTMLResponse)
def hoja(request: Request):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/")
    proyecto = estado.proyecto
    agrupadores = [("", f"(raíz) {proyecto.nombre}")]
    _rutas_agrupadores(proyecto.raiz, "", agrupadores)
    matrices = [r for r in proyecto.catalogo.por_tipo(ic.TipoRecurso.MATRIZ)]
    return templates.TemplateResponse(request, "hoja.html", {
        "nombre_proyecto": proyecto.nombre,
        "agrupadores": agrupadores,
        "matrices": matrices,
        "unidades": sorted(UNIDADES_PREDEFINIDAS),
        "error": request.query_params.get("error"),
        "ok": request.query_params.get("ok"),
    })


def _rutas_agrupadores(nodo: ic.Agrupador, ruta: str, salida: list) -> None:
    for hijo in nodo.hijos:
        if isinstance(hijo, ic.Agrupador):
            ruta_hijo = f"{ruta}/{hijo.clave}" if ruta else hijo.clave
            salida.append((ruta_hijo, f"{hijo.clave} — {hijo.descripcion}"))
            _rutas_agrupadores(hijo, ruta_hijo, salida)


@router.get("/matriz/{clave}", response_class=HTMLResponse)
def ficha(request: Request, clave: str, concepto: str = ""):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/")
    proyecto = estado.proyecto
    try:
        matriz = _matriz(proyecto, clave)
    except ERRORES_MOTOR:
        return RedirectResponse(url="/hoja?error=No existe la matriz")
    recursos = sorted(
        (r for r in proyecto.catalogo.buscar("*") if r.clave != clave),
        key=lambda r: (r.tipo.value, r.clave))
    return templates.TemplateResponse(request, "ficha.html", {
        "nombre_proyecto": proyecto.nombre,
        "clave_matriz": matriz.clave,
        "clave_concepto": concepto,
        "recursos": recursos,
    })


# ================================================================ API JSON
@router.get("/api/hoja")
def api_hoja(request: Request):
    estado = _estado(request)
    if estado is None:
        return _sin_sesion()
    return {"ok": True, "hoja": serializar.filas_hoja(estado.proyecto)}


@router.get("/api/gantt")
def api_gantt(request: Request):
    estado = _estado(request)
    if estado is None:
        return _sin_sesion()
    return {"ok": True, "gantt": serializar.datos_gantt(estado.proyecto)}


@router.get("/api/matriz/{clave}")
def api_matriz(request: Request, clave: str, concepto: str = ""):
    estado = _estado(request)
    if estado is None:
        return _sin_sesion()
    return _payload_ficha(estado.proyecto, clave, concepto)


def _payload_ficha(proyecto: ic.Proyecto, clave: str, concepto: str = ""):
    try:
        matriz = _matriz(proyecto, clave)
        objeto_concepto = _concepto(proyecto, concepto) if concepto else None
    except ERRORES_MOTOR as exc:
        return _error(str(exc), 404)
    return {"ok": True,
            "ficha": serializar.datos_ficha(proyecto, matriz, objeto_concepto)}


def _payload_hoja(proyecto: ic.Proyecto):
    return {"ok": True, "hoja": serializar.filas_hoja(proyecto)}


@router.patch("/api/concepto/{clave}")
def api_editar_concepto(request: Request, clave: str,
                        datos: dict = Body(...)):
    estado = _estado(request)
    if estado is None:
        return _sin_sesion()
    proyecto = estado.proyecto
    try:
        concepto = _concepto(proyecto, clave)
        if "cantidad" in datos:
            if concepto.generador is not None:
                raise ValueError(
                    "La cantidad de este concepto proviene de números "
                    "generadores; edítala en el wizard (paso 4).")
            cantidad = forms.numero(str(datos["cantidad"]))
            ic.D(cantidad)  # valida que sea numérica antes de asignar
            concepto.cantidad = cantidad
        if "descripcion" in datos:
            concepto.descripcion = forms.texto(str(datos["descripcion"]))
    except ERRORES_MOTOR as exc:
        return _error(str(exc))
    return _payload_hoja(proyecto)


@router.patch("/api/agrupador")
def api_editar_agrupador(request: Request, datos: dict = Body(...)):
    estado = _estado(request)
    if estado is None:
        return _sin_sesion()
    proyecto = estado.proyecto
    try:
        agrupador = _agrupador(proyecto.raiz, str(datos.get("ruta", "")))
        if agrupador is proyecto.raiz:
            raise ValueError("La raíz del proyecto no se edita aquí.")
        if "descripcion" in datos:
            agrupador.descripcion = forms.texto(str(datos["descripcion"]))
    except ERRORES_MOTOR as exc:
        return _error(str(exc))
    return _payload_hoja(proyecto)


@router.patch("/api/matriz/{clave}/insumo/{recurso}")
def api_editar_insumo(request: Request, clave: str, recurso: str,
                      datos: dict = Body(...), concepto: str = ""):
    estado = _estado(request)
    if estado is None:
        return _sin_sesion()
    proyecto = estado.proyecto
    try:
        matriz = _matriz(proyecto, clave)
        insumo = next((i for i in matriz.insumos
                       if i.recurso.clave == recurso), None)
        if insumo is None:
            raise KeyError(f"La matriz no contiene el insumo {recurso!r}.")
        if "cantidad" in datos:
            insumo.cantidad = forms.numero(str(datos["cantidad"]), "0")
            insumo.cantidad_decimal  # valida fórmula/número de inmediato
    except ERRORES_MOTOR as exc:
        return _error(str(exc))
    return _payload_ficha(proyecto, clave, concepto)


@router.post("/api/matriz/{clave}/insumo")
def api_agregar_insumo(request: Request, clave: str,
                       datos: dict = Body(...), concepto: str = ""):
    estado = _estado(request)
    if estado is None:
        return _sin_sesion()
    proyecto = estado.proyecto
    try:
        matriz = _matriz(proyecto, clave)
        clave_recurso = forms.texto(str(datos.get("recurso", "")))
        # Acepta "CLAVE — descripción" del datalist o la clave sola.
        clave_recurso = clave_recurso.split("—")[0].strip()
        if not clave_recurso:
            raise ValueError("Indica la clave del recurso a agregar.")
        objeto = proyecto.catalogo.obtener(clave_recurso)
        if any(i.recurso.clave == objeto.clave for i in matriz.insumos):
            raise ValueError(
                f"La matriz ya contiene el insumo {objeto.clave!r}; "
                "edita su cantidad en la celda.")
        cantidad = forms.numero(str(datos.get("cantidad", "1")), "1")
        insumo = matriz.agregar_insumo(objeto, cantidad)
        insumo.cantidad_decimal  # valida
    except ERRORES_MOTOR as exc:
        return _error(str(exc))
    return _payload_ficha(proyecto, clave, concepto)


@router.delete("/api/matriz/{clave}/insumo/{recurso}")
def api_quitar_insumo(request: Request, clave: str, recurso: str,
                      concepto: str = ""):
    estado = _estado(request)
    if estado is None:
        return _sin_sesion()
    proyecto = estado.proyecto
    try:
        matriz = _matriz(proyecto, clave)
        if not any(i.recurso.clave == recurso for i in matriz.insumos):
            raise KeyError(f"La matriz no contiene el insumo {recurso!r}.")
        matriz.quitar_componente(recurso)
    except ERRORES_MOTOR as exc:
        return _error(str(exc))
    return _payload_ficha(proyecto, clave, concepto)


@router.patch("/api/recurso/{clave}")
def api_editar_recurso(request: Request, clave: str,
                       datos: dict = Body(...),
                       matriz: str = "", concepto: str = ""):
    """Edita costo/descripción de un recurso simple desde la ficha.

    ``matriz`` indica desde qué ficha se edita, para devolverla
    recalculada.
    """
    estado = _estado(request)
    if estado is None:
        return _sin_sesion()
    proyecto = estado.proyecto
    try:
        recurso = proyecto.catalogo.obtener(clave)
        if "costo" in datos:
            if recurso.tipo not in serializar.TIPOS_COSTO_EDITABLE \
                    or recurso.es_compuesto or recurso.formula_costo:
                raise ValueError(
                    "El costo de este recurso se calcula (compuesto, "
                    "fórmula, FSR o costo horario); edítalo en el wizard "
                    "(paso 2).")
            recurso.costo = forms.numero(str(datos["costo"]), "0")
            recurso.costo_unitario(proyecto)  # valida
        if "descripcion" in datos:
            recurso.descripcion = forms.texto(str(datos["descripcion"]))
    except ERRORES_MOTOR as exc:
        return _error(str(exc))
    if matriz:
        return _payload_ficha(proyecto, matriz, concepto)
    return _payload_hoja(proyecto)


@router.patch("/api/pie/{identificador}")
def api_editar_pie(request: Request, identificador: str,
                   datos: dict = Body(...), matriz: str = "",
                   concepto: str = ""):
    estado = _estado(request)
    if estado is None:
        return _sin_sesion()
    proyecto = estado.proyecto
    try:
        cargo = proyecto.pie.obtener(identificador)
        if "porcentaje" in datos:
            cargo.porcentaje = ic.D(forms.numero(str(datos["porcentaje"]), "0"))
        if "base" in datos:
            cargo.base = ic.BaseCalculo(str(datos["base"]))
        if "formula" in datos:
            cargo.formula = forms.texto(str(datos["formula"])) or None
    except ERRORES_MOTOR as exc:
        return _error(str(exc))
    if matriz:
        return _payload_ficha(proyecto, matriz, concepto)
    return _payload_hoja(proyecto)


# ============================================================ alta rápida
@router.post("/hoja/capitulo")
def hoja_agregar_capitulo(request: Request,
                          padre: str = Form(""),
                          clave: str = Form(...),
                          descripcion: str = Form("")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)
    try:
        nodo = _agrupador(estado.proyecto.raiz, forms.texto(padre))
        nodo.agregar_agrupador(forms.texto(clave), forms.texto(descripcion))
    except ERRORES_MOTOR as exc:
        return forms.redirigir("/hoja", error=str(exc))
    return forms.redirigir("/hoja", ok=f"Capítulo {clave} agregado.")


@router.post("/hoja/concepto")
def hoja_agregar_concepto(request: Request,
                          padre: str = Form(""),
                          clave: str = Form(...),
                          descripcion: str = Form(""),
                          unidad: str = Form("pza"),
                          cantidad: str = Form("0"),
                          matriz: str = Form("")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)
    proyecto = estado.proyecto
    try:
        nodo = _agrupador(proyecto.raiz, forms.texto(padre))
        clave_limpia = forms.texto(clave)
        if any(c.clave == clave_limpia for c in proyecto.iter_conceptos()):
            raise ValueError(f"Ya existe un concepto con clave {clave_limpia!r}.")
        objeto_matriz = None
        if forms.texto(matriz):
            objeto_matriz = _matriz(proyecto, forms.texto(matriz))
        concepto = ic.Concepto(
            clave=clave_limpia,
            descripcion=forms.texto(descripcion),
            unidad=forms.texto(unidad, "pza"),
            cantidad=forms.numero(cantidad, "0"),
            matriz=objeto_matriz)
        nodo.agregar_concepto(concepto)
    except ERRORES_MOTOR as exc:
        return forms.redirigir("/hoja", error=str(exc))
    return forms.redirigir("/hoja", ok=f"Concepto {clave} agregado.")


# ======================================================== configuración pie
@router.get("/pie", response_class=HTMLResponse)
def pie_config(request: Request):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/")
    proyecto = estado.proyecto
    detalle = proyecto.pie.aplicar(
        proyecto.precision.moneda(proyecto.costo_directo_total()))
    return templates.TemplateResponse(request, "pie_config.html", {
        "nombre_proyecto": proyecto.nombre,
        "pie": serializar._datos_pie(proyecto, detalle),  # noqa: SLF001
        "modos": [m.value for m in ic.ModoPie],
        "bases": [b.value for b in ic.BaseCalculo],
        "error": request.query_params.get("error"),
        "ok": request.query_params.get("ok"),
    })


@router.post("/pie/modo")
def pie_modo(request: Request, modo: str = Form(...)):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)
    try:
        estado.proyecto.pie.modo = ic.ModoPie(modo)
    except ERRORES_MOTOR as exc:
        return forms.redirigir("/pie", error=str(exc))
    return forms.redirigir("/pie", ok=f"Modo {modo} activado.")


@router.post("/pie/cargo")
def pie_agregar_cargo(request: Request,
                      identificador: str = Form(...),
                      nombre: str = Form(...),
                      porcentaje: str = Form("0"),
                      base: str = Form("Acumulable"),
                      formula: str = Form(""),
                      incluye_isn: str = Form(None)):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)
    try:
        estado.proyecto.pie.agregar(
            forms.texto(identificador).upper(), forms.texto(nombre),
            porcentaje=forms.numero(porcentaje, "0"),
            base=ic.BaseCalculo(base),
            formula=forms.texto(formula) or None,
            incluye_isn=forms.marcado(incluye_isn))
    except ERRORES_MOTOR as exc:
        return forms.redirigir("/pie", error=str(exc))
    return forms.redirigir("/pie", ok=f"Cargo {identificador} agregado.")


@router.post("/pie/cargo/{identificador}")
def pie_actualizar_cargo(request: Request, identificador: str,
                         nombre: str = Form(...),
                         porcentaje: str = Form("0"),
                         base: str = Form("Acumulable"),
                         formula: str = Form(""),
                         incluye_isn: str = Form(None)):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)
    try:
        cargo = estado.proyecto.pie.obtener(identificador)
        cargo.nombre = forms.texto(nombre, cargo.nombre)
        cargo.porcentaje = ic.D(forms.numero(porcentaje, "0"))
        cargo.base = ic.BaseCalculo(base)
        cargo.formula = forms.texto(formula) or None
        cargo.incluye_isn = forms.marcado(incluye_isn)
    except ERRORES_MOTOR as exc:
        return forms.redirigir("/pie", error=str(exc))
    return forms.redirigir("/pie", ok=f"Cargo {identificador} actualizado.")


@router.post("/pie/cargo/{identificador}/eliminar")
def pie_eliminar_cargo(request: Request, identificador: str):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)
    pie = estado.proyecto.pie
    if not any(c.identificador == identificador for c in pie.cargos):
        return forms.redirigir("/pie", error=f"No existe el cargo {identificador}.")
    pie.cargos = [c for c in pie.cargos if c.identificador != identificador]
    return forms.redirigir("/pie", ok=f"Cargo {identificador} eliminado.")
