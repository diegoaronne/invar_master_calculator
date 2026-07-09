"""INVAR Master Calculator — Web App (prototipo).

Correr desde la raíz del repo (donde vive invar_calculator/):
    uvicorn webapp.main:app --reload

Login demo: contraseña tomada de la variable de entorno
INVAR_DEMO_PASSWORD; si no está definida se usa el default de desarrollo
"invar2026" (no compartir el link públicamente sin definir la variable).
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import demo_seed, session_store
from .routers import hoja, insumos, reportes, wizard

DEMO_PASSWORD = os.environ.get("INVAR_DEMO_PASSWORD", "")
if not DEMO_PASSWORD:
    DEMO_PASSWORD = "invar2026"
    logging.getLogger("invar.webapp").warning(
        "INVAR_DEMO_PASSWORD no está definida; usando la clave de "
        "desarrollo. Define la variable de entorno antes de un deploy "
        "público.")

app = FastAPI(title="INVAR Master Calculator")
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")
templates = Jinja2Templates(directory="webapp/templates")
app.include_router(reportes.router)
app.include_router(wizard.router)
app.include_router(hoja.router)
app.include_router(insumos.router)


def _estado_sesion(request: Request):
    session_id = request.cookies.get("session_id")
    return session_store.get(session_id) if session_id else None


@app.get("/", response_class=HTMLResponse)
def login_form(request: Request):
    if _estado_sesion(request) is not None:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
def login(password: str = Form(...)):
    if password != DEMO_PASSWORD:
        return RedirectResponse(url="/?error=1", status_code=303)

    session_id = session_store.new_session_id()
    session_store.put(session_id, demo_seed.construir_estado_demo())

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    estado = _estado_sesion(request)
    if estado is None:
        return RedirectResponse(url="/")
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "nombre_proyecto": estado.proyecto.nombre,
            "ok": request.query_params.get("ok"),
        },
    )


@app.post("/proyecto/nuevo")
def proyecto_nuevo(request: Request):
    """Reemplaza el proyecto de la sesión por uno en blanco (wizard
    desde cero)."""
    session_id = request.cookies.get("session_id")
    if not session_id or session_store.get(session_id) is None:
        return RedirectResponse(url="/", status_code=303)
    session_store.put(session_id, demo_seed.construir_estado_vacio())
    return RedirectResponse(url="/wizard/1", status_code=303)


@app.post("/proyecto/plantilla")
def proyecto_plantilla(request: Request):
    """Reemplaza el proyecto de la sesión por una copia del demo, para
    usarlo como plantilla y solo ajustar datos/cantidades. Como ya viene
    configurado, aterriza directo en la hoja de presupuesto."""
    session_id = request.cookies.get("session_id")
    if not session_id or session_store.get(session_id) is None:
        return RedirectResponse(url="/", status_code=303)
    session_store.put(session_id, demo_seed.construir_estado_demo())
    return RedirectResponse(url="/hoja", status_code=303)


@app.post("/reset-demo")
def reset_demo(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        session_store.reset(session_id, demo_seed.construir_estado_demo)
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/logout")
def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        session_store.drop(session_id)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_id")
    return response
