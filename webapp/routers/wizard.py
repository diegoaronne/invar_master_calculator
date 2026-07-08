"""Wizard de captura de proyectos — pasos 1 a 6 del brief técnico.

Cada paso es un GET (formulario + estado actual) y uno o varios POST
pequeños que traducen el formulario a llamadas del motor y redirigen de
vuelta al paso (patrón post/redirect/get, con ?ok= / ?error= como flash).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import invar_calculator as ic
from invar_calculator.modelos import UNIDADES_PREDEFINIDAS
from invar_calculator.proyecto import NOMBRE_MAXIMO

from .. import forms, session_store
from ..estado import EstadoSesion

router = APIRouter(prefix="/wizard")
templates = Jinja2Templates(directory="webapp/templates")

PASOS = [
    (1, "Datos generales"),
    (2, "Catálogo de recursos"),
    (3, "Matrices de PU"),
    (4, "WBS y conceptos"),
    (5, "Calendario y programa"),
    (6, "Sobrecostos"),
]


def _estado(request: Request) -> Optional[EstadoSesion]:
    session_id = request.cookies.get("session_id")
    return session_store.get(session_id) if session_id else None


def _ctx_base(request: Request, estado: EstadoSesion, paso: int) -> dict:
    return {
        "paso": paso,
        "pasos": PASOS,
        "nombre_proyecto": estado.proyecto.nombre,
        "error": request.query_params.get("error"),
        "ok": request.query_params.get("ok"),
        "unidades": sorted(UNIDADES_PREDEFINIDAS),
    }


def _agrupadores_con_ruta(raiz: ic.Agrupador) -> List[Tuple[str, ic.Agrupador]]:
    """Aplana el árbol WBS en pares (ruta-de-claves, agrupador)."""
    resultado: List[Tuple[str, ic.Agrupador]] = []

    def visitar(nodo: ic.Agrupador, ruta: str) -> None:
        for hijo in nodo.hijos:
            if isinstance(hijo, ic.Agrupador):
                ruta_hijo = f"{ruta}/{hijo.clave}" if ruta else hijo.clave
                resultado.append((ruta_hijo, hijo))
                visitar(hijo, ruta_hijo)

    visitar(raiz, "")
    return resultado


def _agrupador_por_ruta(raiz: ic.Agrupador, ruta: str) -> ic.Agrupador:
    if not ruta:  # raíz del proyecto
        return raiz
    for r, agrupador in _agrupadores_con_ruta(raiz):
        if r == ruta:
            return agrupador
    raise ValueError(f"No existe el agrupador {ruta!r}.")


def _concepto_por_clave(proyecto: ic.Proyecto, clave: str) -> ic.Concepto:
    for concepto in proyecto.iter_conceptos():
        if concepto.clave == clave:
            return concepto
    raise ValueError(f"No existe el concepto {clave!r}.")


def _render_paso(request: Request, estado: EstadoSesion, paso: int,
                 plantilla: str, extra: dict) -> HTMLResponse:
    ctx = _ctx_base(request, estado, paso)
    ctx.update(extra)
    return templates.TemplateResponse(request, plantilla, ctx)


def _post_seguro(request: Request, paso: int, accion) -> RedirectResponse:
    """Ejecuta la acción de un POST y traduce errores del motor a flash."""
    url = f"/wizard/{paso}"
    try:
        mensaje = accion()
    except (ValueError, ArithmeticError, KeyError) as exc:
        return forms.redirigir(url, error=str(exc))
    return forms.redirigir(url, ok=mensaje or "Guardado.")


# ---------------------------------------------------------------- paso 1
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def wizard_inicio(request: Request):
    return RedirectResponse(url="/wizard/1")


@router.get("/1", response_class=HTMLResponse)
def paso1(request: Request):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/")
    return _render_paso(request, estado, 1, "wizard1.html", {
        "proyecto": estado.proyecto,
        "datos": estado.proyecto.datos,
    })


@router.post("/1")
def paso1_guardar(request: Request,
                  nombre: str = Form(...),
                  cliente: str = Form(""),
                  autor: str = Form(""),
                  descripcion_obra: str = Form(""),
                  ubicacion: str = Form(""),
                  fecha_inicio: str = Form(""),
                  fecha_fin: str = Form(""),
                  responsables: str = Form(""),
                  iva_pct: str = Form("16")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        p = estado.proyecto
        nombre_limpio = forms.texto(nombre)
        if not nombre_limpio or len(nombre_limpio) > NOMBRE_MAXIMO:
            raise ValueError(
                f"El nombre debe tener entre 1 y {NOMBRE_MAXIMO} caracteres.")
        p.nombre = nombre_limpio
        p.iva_pct = ic.D(forms.numero(iva_pct, "16"))
        p.datos = ic.DatosGenerales(
            cliente=forms.texto(cliente),
            autor=forms.texto(autor),
            descripcion_obra=forms.texto(descripcion_obra),
            ubicacion=forms.texto(ubicacion),
            fecha_inicio=forms.fecha(fecha_inicio),
            fecha_fin=forms.fecha(fecha_fin),
            responsables=[r.strip() for r in responsables.splitlines()
                          if r.strip()],
        )
        inicio, fin = p.datos.fecha_inicio, p.datos.fecha_fin
        p.programa.fecha_inicio_proyecto = inicio
        p.programa.fecha_fin_proyecto = fin
        return "Datos generales guardados."

    return _post_seguro(request, 1, accion)


# ---------------------------------------------------------------- paso 2
@router.get("/2", response_class=HTMLResponse)
def paso2(request: Request):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/")
    cat = estado.proyecto.catalogo
    tr = ic.TipoRecurso
    mano_obra = cat.por_tipo(tr.MANO_OBRA)
    return _render_paso(request, estado, 2, "wizard2.html", {
        "proyecto": estado.proyecto,
        "materiales": cat.por_tipo(tr.MATERIAL),
        "mano_obra_simple": [r for r in mano_obra if not r.componentes],
        "cuadrillas": [r for r in mano_obra if r.componentes],
        "herramientas": cat.por_tipo(tr.HERRAMIENTA),
        "equipos": cat.por_tipo(tr.EQUIPO),
        "auxiliares": cat.por_tipo(tr.AUXILIAR),
        "hoja_fsr": estado.proyecto.hoja_fsr,
    })


@router.post("/2/fsr")
def paso2_fsr(request: Request,
              salario_minimo: str = Form(...),
              prima_riesgo_pct: str = Form(...),
              isn_pct: str = Form("3.0"),
              incluir_isn: Optional[str] = Form(None),
              dias_por_clima: str = Form("0")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        estado.proyecto.hoja_fsr = ic.HojaFSR(
            salario_minimo_general=forms.numero(salario_minimo),
            prima_riesgo_pct=forms.numero(prima_riesgo_pct),
            isn_pct=forms.numero(isn_pct, "3.0"),
            incluir_isn=forms.marcado(incluir_isn),
            calendario=ic.CalendarioLaboralAnual(
                dias_por_clima=forms.entero(dias_por_clima)),
            precision=estado.proyecto.precision,
        )
        return "FSR actualizado."

    return _post_seguro(request, 2, accion)


@router.post("/2/material")
def paso2_material(request: Request,
                   clave: str = Form(...),
                   descripcion: str = Form(""),
                   unidad: str = Form("pza"),
                   costo: str = Form("0"),
                   familia: str = Form(""),
                   indivisible: Optional[str] = Form(None)):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        estado.proyecto.catalogo.crear(
            forms.texto(clave), descripcion=forms.texto(descripcion),
            unidad=forms.texto(unidad, "pza"), costo=forms.numero(costo),
            familia=forms.texto(familia),
            indivisible=forms.marcado(indivisible))
        return f"Material {clave!r} agregado."

    return _post_seguro(request, 2, accion)


@router.post("/2/mano-obra")
def paso2_mano_obra(request: Request,
                    clave: str = Form(...),
                    descripcion: str = Form(""),
                    salario_base: str = Form(...),
                    usa_fsr: Optional[str] = Form(None),
                    fsr_manual: str = Form("")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        estado.proyecto.catalogo.registrar(ic.Recurso(
            forms.texto(clave), forms.texto(descripcion), "jor",
            ic.TipoRecurso.MANO_OBRA,
            salario_base=forms.numero(salario_base),
            usa_fsr=forms.marcado(usa_fsr),
            fsr_manual=forms.numero_opcional(fsr_manual)))
        return f"Mano de obra {clave!r} agregada."

    return _post_seguro(request, 2, accion)


@router.post("/2/herramienta")
def paso2_herramienta(request: Request,
                      clave: str = Form(...),
                      descripcion: str = Form("")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        # Unidad %mo: su costo se calcula como porcentaje de la mano de
        # obra de la matriz donde participa (video 17).
        estado.proyecto.catalogo.registrar(ic.Recurso(
            forms.texto(clave), forms.texto(descripcion), "%mo",
            ic.TipoRecurso.HERRAMIENTA))
        return f"Herramienta {clave!r} agregada."

    return _post_seguro(request, 2, accion)


@router.post("/2/compuesto")
def paso2_compuesto(request: Request,
                    tipo: str = Form(...),
                    clave: str = Form(...),
                    descripcion: str = Form(""),
                    unidad: str = Form("jor")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        tipos = {"cuadrilla": ic.TipoRecurso.MANO_OBRA,
                 "auxiliar": ic.TipoRecurso.AUXILIAR}
        if tipo not in tipos:
            raise ValueError("Tipo de compuesto no válido.")
        unidad_final = "jor" if tipo == "cuadrilla" else forms.texto(unidad, "m3")
        estado.proyecto.catalogo.registrar(ic.Recurso(
            forms.texto(clave), forms.texto(descripcion), unidad_final,
            tipos[tipo]))
        return (f"{'Cuadrilla' if tipo == 'cuadrilla' else 'Auxiliar'} "
                f"{clave!r} creado; agrégale componentes.")

    return _post_seguro(request, 2, accion)


@router.post("/2/componente")
def paso2_componente(request: Request,
                     padre: str = Form(...),
                     recurso: str = Form(...),
                     cantidad: str = Form("1")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        cat = estado.proyecto.catalogo
        compuesto = cat.obtener(forms.texto(padre))
        componente = cat.obtener(forms.texto(recurso))
        # La cantidad admite fórmulas tipo "1/10" (mandos proporcionales).
        compuesto.agregar_componente(componente, forms.numero(cantidad, "1"))
        return f"Componente {recurso!r} agregado a {padre!r}."

    return _post_seguro(request, 2, accion)


@router.post("/2/equipo")
def paso2_equipo(request: Request,
                 clave: str = Form(...),
                 descripcion: str = Form(""),
                 valor_adquisicion: str = Form("0"),
                 valor_llantas: str = Form("0"),
                 porcentaje_rescate: str = Form("10"),
                 vida_economica_anios: str = Form("5"),
                 horas_por_anio: str = Form("2000"),
                 tasa_interes_anual_pct: str = Form("12"),
                 prima_seguro_anual_pct: str = Form("3"),
                 factor_mantenimiento: str = Form("0.80"),
                 potencia_hp: str = Form("0"),
                 factor_operacion: str = Form("0.80"),
                 coeficiente_combustible: str = Form("0.1514"),
                 precio_combustible: str = Form("0"),
                 capacidad_carter: str = Form("0"),
                 horas_entre_cambios_aceite: str = Form("100"),
                 precio_lubricante: str = Form("0"),
                 vida_llantas_horas: str = Form("0"),
                 operador_puesto: str = Form(""),
                 operador_salario_turno: str = Form("0"),
                 horas_efectivas_turno: str = Form("8")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        operadores = []
        if forms.texto(operador_puesto):
            operadores.append(ic.Operador(
                forms.texto(operador_puesto),
                forms.numero(operador_salario_turno)))
        equipo = ic.Recurso(forms.texto(clave), forms.texto(descripcion),
                            "hr", ic.TipoRecurso.EQUIPO)
        equipo.datos_costo_horario = ic.DatosCostoHorario(
            valor_adquisicion=forms.numero(valor_adquisicion),
            valor_llantas=forms.numero(valor_llantas),
            porcentaje_rescate=forms.numero(porcentaje_rescate, "10"),
            vida_economica_anios=forms.numero(vida_economica_anios, "5"),
            horas_por_anio=forms.numero(horas_por_anio, "2000"),
            tasa_interes_anual_pct=forms.numero(tasa_interes_anual_pct, "12"),
            prima_seguro_anual_pct=forms.numero(prima_seguro_anual_pct, "3"),
            factor_mantenimiento=forms.numero(factor_mantenimiento, "0.80"),
            potencia_hp=forms.numero(potencia_hp),
            factor_operacion=forms.numero(factor_operacion, "0.80"),
            coeficiente_combustible=forms.numero(coeficiente_combustible,
                                                 "0.1514"),
            precio_combustible=forms.numero(precio_combustible),
            capacidad_carter=forms.numero(capacidad_carter),
            horas_entre_cambios_aceite=forms.numero(
                horas_entre_cambios_aceite, "100"),
            precio_lubricante=forms.numero(precio_lubricante),
            vida_llantas_horas=forms.numero(vida_llantas_horas),
            operadores=operadores,
            horas_efectivas_turno=forms.numero(horas_efectivas_turno, "8"),
        )
        estado.proyecto.catalogo.registrar(equipo)
        return f"Equipo {clave!r} agregado con costo horario."

    return _post_seguro(request, 2, accion)


# ---------------------------------------------------------------- paso 3
@router.get("/3", response_class=HTMLResponse)
def paso3(request: Request):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/")
    p = estado.proyecto
    matrices = p.catalogo.por_tipo(ic.TipoRecurso.MATRIZ)
    recursos = [r for t in ic.TipoRecurso if t != ic.TipoRecurso.MATRIZ
                for r in p.catalogo.por_tipo(t)]
    detalle = [(m, [(i, i.recurso) for i in m.insumos],
                p.precision.moneda(m.costo_unitario(p)))
               for m in matrices]
    return _render_paso(request, estado, 3, "wizard3.html", {
        "detalle_matrices": detalle,
        "recursos": recursos,
    })


@router.post("/3/matriz")
def paso3_matriz(request: Request,
                 clave: str = Form(...),
                 descripcion: str = Form(""),
                 unidad: str = Form("pza")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        estado.proyecto.crear_matriz(
            forms.texto(clave), forms.texto(descripcion),
            forms.texto(unidad, "pza"))
        return f"Matriz {clave!r} creada; agrégale insumos."

    return _post_seguro(request, 3, accion)


@router.post("/3/insumo")
def paso3_insumo(request: Request,
                 matriz: str = Form(...),
                 recurso: str = Form(...),
                 cantidad: str = Form("1")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        cat = estado.proyecto.catalogo
        destino = cat.obtener(forms.texto(matriz))
        if not isinstance(destino, ic.Matriz):
            raise ValueError(f"{matriz!r} no es una matriz.")
        destino.agregar_insumo(cat.obtener(forms.texto(recurso)),
                               forms.numero(cantidad, "1"))
        return f"Insumo {recurso!r} agregado a {matriz!r}."

    return _post_seguro(request, 3, accion)


# ---------------------------------------------------------------- paso 4
@router.get("/4", response_class=HTMLResponse)
def paso4(request: Request):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/")
    p = estado.proyecto
    arbol = list(p.raiz.iter_nodos())
    conceptos = list(p.iter_conceptos())
    return _render_paso(request, estado, 4, "wizard4.html", {
        "proyecto": p,
        "arbol": arbol,
        "agrupadores": _agrupadores_con_ruta(p.raiz),
        "matrices": p.catalogo.por_tipo(ic.TipoRecurso.MATRIZ),
        "conceptos": conceptos,
        "es_agrupador": lambda nodo: isinstance(nodo, ic.Agrupador),
    })


@router.post("/4/agrupador")
def paso4_agrupador(request: Request,
                    padre: str = Form(""),
                    clave: str = Form(...),
                    descripcion: str = Form("")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        destino = _agrupador_por_ruta(estado.proyecto.raiz, forms.texto(padre))
        destino.agregar_agrupador(forms.texto(clave),
                                  forms.texto(descripcion))
        return f"Agrupador {clave!r} agregado."

    return _post_seguro(request, 4, accion)


@router.post("/4/concepto")
def paso4_concepto(request: Request,
                   agrupador: str = Form(...),
                   clave: str = Form(...),
                   descripcion: str = Form(""),
                   unidad: str = Form("pza"),
                   cantidad: str = Form("0"),
                   matriz: str = Form("")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        p = estado.proyecto
        destino = _agrupador_por_ruta(p.raiz, forms.texto(agrupador))
        matriz_obj = None
        if forms.texto(matriz):
            matriz_obj = p.catalogo.obtener(forms.texto(matriz))
            if not isinstance(matriz_obj, ic.Matriz):
                raise ValueError(f"{matriz!r} no es una matriz.")
        destino.agregar_concepto(ic.Concepto(
            forms.texto(clave), forms.texto(descripcion),
            forms.texto(unidad, "pza"),
            cantidad=forms.numero(cantidad), matriz=matriz_obj))
        return f"Concepto {clave!r} agregado."

    return _post_seguro(request, 4, accion)


@router.post("/4/generador")
def paso4_generador(request: Request,
                    concepto: str = Form(...),
                    referencia: str = Form(""),
                    largo: str = Form(""),
                    ancho: str = Form(""),
                    alto: str = Form(""),
                    piezas: str = Form("1"),
                    cantidad_directa: str = Form("")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        p = estado.proyecto
        objetivo = _concepto_por_clave(p, forms.texto(concepto))
        if objetivo.generador is None:
            objetivo.generador = ic.NumerosGeneradores(p.precision)
        objetivo.generador.agregar(
            referencia=forms.texto(referencia),
            largo=forms.numero_opcional(largo),
            ancho=forms.numero_opcional(ancho),
            alto=forms.numero_opcional(alto),
            piezas=forms.numero(piezas, "1"),
            cantidad_directa=forms.numero_opcional(cantidad_directa))
        total = objetivo.generador.cantidad_total()
        return (f"Línea agregada al generador de {concepto!r} "
                f"(cantidad total: {total}).")

    return _post_seguro(request, 4, accion)


# ---------------------------------------------------------------- paso 5
@router.get("/5", response_class=HTMLResponse)
def paso5(request: Request):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/")
    p = estado.proyecto
    actividades = []
    criticas = []
    if p.programa.actividades:
        try:
            criticas = p.programa.actividades_criticas()
        except ValueError:
            criticas = []
    for idx, act in enumerate(p.programa.actividades):
        actividades.append({
            "indice": idx,
            "clave": act.concepto.clave,
            "descripcion": act.concepto.descripcion,
            "inicio": act.fecha_inicio(p.programa.calendario),
            "fin": act.fecha_fin(p.programa.calendario),
            "duracion": act.duracion_laborable,
            "porcentaje": act.porcentaje_programado(),
            "critica": act in criticas,
        })
    return _render_paso(request, estado, 5, "wizard5.html", {
        "proyecto": p,
        "conceptos": list(p.iter_conceptos()),
        "actividades": actividades,
        "alertas": (p.programa.alertas
                    + p.programa.validar_fraccionamiento()),
        # El calendario no expone públicamente sus excepciones; para el
        # resumen visual del wizard leemos el detalle interno sin mutarlo.
        "excepciones": sorted(
            getattr(p.calendario, "_excepciones", {}).items()),
    })


@router.post("/5/calendario")
def paso5_calendario(request: Request,
                     fecha: str = Form(...),
                     fecha_hasta: str = Form(""),
                     estado_dia: str = Form(...),
                     horas: str = Form("")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        estados = {e.name: e for e in ic.EstadoDia}
        if estado_dia not in estados:
            raise ValueError("Estado de día no válido.")
        inicio = forms.fecha(fecha)
        fin = forms.fecha(fecha_hasta) or inicio
        if fin < inicio:
            raise ValueError("La fecha final es anterior a la inicial.")
        estado.proyecto.calendario.marcar_rango(
            inicio, fin, estados[estado_dia],
            horas=forms.numero_opcional(horas))
        dias = (fin - inicio).days + 1
        return f"{dias} día(s) marcados como {estados[estado_dia].value}."

    return _post_seguro(request, 5, accion)


@router.post("/5/actividad")
def paso5_actividad(request: Request,
                    concepto: str = Form(...),
                    inicio: str = Form(...),
                    duracion: str = Form(...),
                    porcentaje: str = Form("100"),
                    predecesoras: List[str] = Form([])):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        p = estado.proyecto
        objetivo = _concepto_por_clave(p, forms.texto(concepto))
        previas = [p.programa.actividades[int(i)] for i in predecesoras]
        p.programa.programar(
            objetivo, forms.fecha(inicio), forms.entero(duracion),
            porcentaje=forms.numero(porcentaje, "100"),
            predecesoras=previas or None)
        return f"Actividad para {concepto!r} programada."

    return _post_seguro(request, 5, accion)


@router.post("/5/segmento")
def paso5_segmento(request: Request,
                   actividad: str = Form(...),
                   inicio: str = Form(...),
                   duracion: str = Form(...),
                   porcentaje: str = Form(...)):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        p = estado.proyecto
        act = p.programa.actividades[forms.entero(actividad)]
        act.agregar_segmento(forms.fecha(inicio), forms.entero(duracion),
                             forms.numero(porcentaje, "100"))
        return (f"Etapa agregada a {act.concepto.clave!r} "
                f"({act.porcentaje_programado()}% programado).")

    return _post_seguro(request, 5, accion)


@router.post("/5/sincronizar")
def paso5_sincronizar(request: Request):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        estado.proyecto.programa.sincronizar_fechas()
        inicio, fin = estado.proyecto.programa.fechas_programa()
        return f"Fechas del proyecto sincronizadas: {inicio} → {fin}."

    return _post_seguro(request, 5, accion)


# ---------------------------------------------------------------- paso 6
@router.get("/6", response_class=HTMLResponse)
def paso6(request: Request):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/")
    p = estado.proyecto
    resumen = None
    try:
        resumen = p.recalcular()
    except (ValueError, ArithmeticError):
        pass
    detalle_pie = None
    if resumen is not None:
        detalle_pie = p.pie.aplicar(resumen.costo_directo)
    return _render_paso(request, estado, 6, "wizard6.html", {
        "proyecto": p,
        "estado_sesion": estado,
        "resumen": resumen,
        "detalle_pie": detalle_pie,
        "metodos_oficina": list(ic.MetodoOficinaCentral),
        "zonas": list(ic.Zona),
        "avisos": estado.avisos,
    })


@router.post("/6/indirectos")
def paso6_indirectos(request: Request,
                     metodo: str = Form(...),
                     porcentaje_gasto_total: str = Form("0"),
                     gasto_anual_oficina: str = Form("0"),
                     ingresos_anuales_obras: str = Form("0"),
                     duracion_obra_meses: str = Form("0")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        metodos = {m.name: m for m in ic.MetodoOficinaCentral}
        if metodo not in metodos:
            raise ValueError("Método de oficina central no válido.")
        estado.indirectos = ic.CalculoIndirectos(
            metodo_oficina_central=metodos[metodo],
            porcentaje_gasto_total=forms.numero(porcentaje_gasto_total),
            gasto_anual_oficina=forms.numero(gasto_anual_oficina),
            ingresos_anuales_obras=forms.numero(ingresos_anuales_obras),
            duracion_obra_meses=forms.numero(duracion_obra_meses),
            precision=estado.proyecto.precision)
        return "Indirectos configurados; agrega personal y gastos abajo."

    return _post_seguro(request, 6, accion)


@router.post("/6/indirectos/personal")
def paso6_personal(request: Request,
                   puesto: str = Form(...),
                   salario_mensual: str = Form(...),
                   meses: str = Form(...),
                   zona: str = Form("CAMPO"),
                   usa_fsr: Optional[str] = Form(None),
                   cantidad: str = Form("1")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        if estado.indirectos is None:
            raise ValueError("Primero configura el cálculo de indirectos.")
        zonas = {z.name: z for z in ic.Zona}
        estado.indirectos.agregar_personal(ic.PersonalIndirecto(
            forms.texto(puesto), forms.numero(salario_mensual),
            forms.numero(meses), zona=zonas[zona],
            usa_fsr=forms.marcado(usa_fsr),
            cantidad=forms.numero(cantidad, "1")))
        return f"Personal {puesto!r} agregado a indirectos."

    return _post_seguro(request, 6, accion)


@router.post("/6/indirectos/gasto")
def paso6_gasto(request: Request,
                concepto: str = Form(...),
                importe_mensual: str = Form(...),
                meses: str = Form(...),
                zona: str = Form("CAMPO")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        if estado.indirectos is None:
            raise ValueError("Primero configura el cálculo de indirectos.")
        zonas = {z.name: z for z in ic.Zona}
        estado.indirectos.agregar_gasto(ic.GastoIndirecto(
            forms.texto(concepto), forms.numero(importe_mensual),
            forms.numero(meses), zona=zonas[zona]))
        return f"Gasto {concepto!r} agregado a indirectos."

    return _post_seguro(request, 6, accion)


@router.post("/6/financiamiento")
def paso6_financiamiento(request: Request,
                         tasa_activa: str = Form(...),
                         tasa_pasiva: str = Form("0"),
                         desfase_cobro: str = Form("1"),
                         anticipo_pct: str = Form("0")):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        estado.financiamiento = ic.CalculoFinanciamiento(
            tasa_activa_anual_pct=forms.numero(tasa_activa),
            tasa_pasiva_anual_pct=forms.numero(tasa_pasiva),
            desfase_cobro_periodos=forms.entero(desfase_cobro, 1),
            anticipo_pct=forms.numero(anticipo_pct),
            precision=estado.proyecto.precision)
        return "Financiamiento configurado."

    return _post_seguro(request, 6, accion)


@router.post("/6/utilidad")
def paso6_utilidad(request: Request,
                   isr_pct: str = Form("30"),
                   ptu_pct: str = Form("10"),
                   utilidad_neta_pct: str = Form(...)):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        estado.utilidad = ic.CalculoUtilidad(
            isr_pct=forms.numero(isr_pct, "30"),
            ptu_pct=forms.numero(ptu_pct, "10"),
            utilidad_neta_pct=forms.numero(utilidad_neta_pct),
            precision=estado.proyecto.precision)
        return "Utilidad configurada."

    return _post_seguro(request, 6, accion)


@router.post("/6/adicionales")
def paso6_adicionales(request: Request,
                      porcentaje: str = Form(...)):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        estado.adicionales_pct = forms.numero(porcentaje)
        return "Cargos adicionales configurados."

    return _post_seguro(request, 6, accion)


@router.post("/6/aplicar")
def paso6_aplicar(request: Request):
    estado = _estado(request)
    if estado is None:
        return RedirectResponse(url="/", status_code=303)

    def accion():
        avisos = estado.aplicar_sobrecostos()
        if avisos:
            return "Sobrecostos aplicados con avisos: " + " · ".join(avisos)
        return "Sobrecostos aplicados al pie de precios."

    return _post_seguro(request, 6, accion)
