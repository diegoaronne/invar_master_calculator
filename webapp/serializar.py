"""Serialización del proyecto a JSON para la interfaz tipo OPUS.

Convierte el estado del motor (Decimal, árboles WBS, programa) en dicts
listos para la hoja de presupuesto (tree-grid), la ficha de costeo de una
matriz y el Gantt del programa de obra. Toda cifra se entrega dos veces:

- ``*_fmt``: formateada con separador de miles para mostrar.
- valor crudo (str) apto para un ``<input>`` editable; conserva fórmulas
  ("1/10") tal como las capturó el usuario.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import invar_calculator as ic
from invar_calculator.modelos import Agrupador, Concepto, Matriz, TipoRecurso

#: Orden de las pestañas de tipo en la ficha de costeo (estilo OPUS).
ORDEN_TIPOS = [
    TipoRecurso.MATERIAL, TipoRecurso.MANO_OBRA, TipoRecurso.HERRAMIENTA,
    TipoRecurso.EQUIPO, TipoRecurso.AUXILIAR, TipoRecurso.FLETE,
    TipoRecurso.SUBCONTRATO, TipoRecurso.MATRIZ,
]


def fmt(valor: Decimal | int | float) -> str:
    return f"{Decimal(valor):,.2f}"


def crudo(valor) -> str:
    """Valor editable tal cual: respeta fórmulas capturadas como texto."""
    if valor is None:
        return ""
    return str(valor)


def _pct(importe: Decimal, total: Decimal) -> str:
    if not total:
        return "0.00"
    return f"{importe / total * 100:.2f}"


# ------------------------------------------------------------------ hoja
def filas_hoja(proyecto: ic.Proyecto) -> dict:
    """Filas del tree-grid + resumen del presupuesto.

    Cada fila lleva ``id`` estable (``a:<ruta>`` para agrupadores,
    ``c:<clave>`` para conceptos) y ``padre`` (id del agrupador que la
    contiene) para que el cliente resuelva expand/collapse y el Gantt
    alinee sus barras.
    """
    resumen = proyecto.recalcular()
    venta_total = resumen.precio_venta
    filas: List[dict] = []

    def visitar(nodo: Agrupador, ruta: str, id_padre: str, nivel: int) -> None:
        for hijo in nodo.hijos:
            if isinstance(hijo, Agrupador):
                ruta_hijo = f"{ruta}/{hijo.clave}" if ruta else hijo.clave
                importe = hijo.importe(proyecto)
                filas.append({
                    "id": f"a:{ruta_hijo}",
                    "padre": id_padre,
                    "tipo": "agrupador",
                    "nivel": nivel,
                    "clave": hijo.clave,
                    "ruta": ruta_hijo,
                    "descripcion": hijo.descripcion,
                    "unidad": "",
                    "cantidad": "",
                    "pu_fmt": "",
                    "importe_fmt": fmt(importe),
                    "pct": _pct(importe, venta_total),
                })
                visitar(hijo, ruta_hijo, f"a:{ruta_hijo}", nivel + 1)
            else:
                filas.append(_fila_concepto(proyecto, hijo, id_padre,
                                            nivel, venta_total))

    visitar(proyecto.raiz, "", "", 1)
    return {
        "filas": filas,
        "resumen": {
            "costo_directo": fmt(resumen.costo_directo),
            "precio_venta": fmt(resumen.precio_venta),
            "iva": fmt(resumen.iva),
            "total_con_iva": fmt(resumen.total_con_iva),
        },
    }


def _fila_concepto(proyecto: ic.Proyecto, concepto: Concepto, id_padre: str,
                   nivel: int, venta_total: Decimal) -> dict:
    mon = proyecto.precision.moneda
    pu_directo = mon(concepto.costo_directo_unitario(proyecto))
    pu_venta = mon(proyecto.pie.precio_venta(pu_directo))
    cantidad = concepto.cantidad_efectiva
    importe = mon(pu_venta * cantidad)
    return {
        "id": f"c:{concepto.clave}",
        "padre": id_padre,
        "tipo": "concepto",
        "nivel": nivel,
        "clave": concepto.clave,
        "descripcion": concepto.descripcion,
        "unidad": concepto.unidad,
        "cantidad": crudo(concepto.cantidad) if concepto.generador is None
                    else str(cantidad),
        "cantidad_fmt": fmt(cantidad),
        "tiene_generador": concepto.generador is not None,
        "matriz": concepto.matriz.clave if concepto.matriz else "",
        "pu_directo_fmt": fmt(pu_directo),
        "pu_fmt": fmt(pu_venta),
        "importe_fmt": fmt(importe),
        "pct": _pct(importe, venta_total),
    }


# ------------------------------------------------------------------ ficha
#: Tipos cuyo costo se captura directo y puede editarse en la celda.
TIPOS_COSTO_EDITABLE = {TipoRecurso.MATERIAL, TipoRecurso.FLETE,
                        TipoRecurso.SUBCONTRATO}


def datos_ficha(proyecto: ic.Proyecto, matriz: Matriz,
                concepto: Optional[Concepto] = None) -> dict:
    """Ficha de costeo completa: insumos, subtotales por tipo y pie."""
    mon = proyecto.precision.moneda
    cd_unitario = mon(matriz.costo_unitario(proyecto))
    costo_mo = sum(
        (i.cantidad_decimal * i.recurso.costo_unitario(proyecto)
         for i in matriz.insumos
         if i.recurso.tipo == TipoRecurso.MANO_OBRA), Decimal(0))

    insumos = [_fila_insumo(proyecto, insumo, costo_mo)
               for insumo in matriz.insumos]

    resumen = matriz.resumen_por_tipo(proyecto)
    subtotales = [{"tipo": "Todos", "importe_fmt": fmt(cd_unitario)}]
    for tipo in ORDEN_TIPOS:
        if tipo.value in resumen:
            subtotales.append({
                "tipo": tipo.value,
                "importe_fmt": fmt(mon(resumen[tipo.value])),
            })

    detalle_pie = proyecto.pie.aplicar(cd_unitario)
    conceptos_vinculados = [
        c.clave for c in proyecto.iter_conceptos()
        if c.matriz is matriz]

    datos = {
        "matriz": {
            "clave": matriz.clave,
            "descripcion": matriz.descripcion,
            "unidad": matriz.unidad,
        },
        "costo_directo_fmt": fmt(cd_unitario),
        "precio_venta_fmt": fmt(detalle_pie.precio_venta),
        "insumos": insumos,
        "subtotales": subtotales,
        "pie": _datos_pie(proyecto, detalle_pie),
        "conceptos_vinculados": conceptos_vinculados,
    }
    if concepto is not None:
        cantidad = concepto.cantidad_efectiva
        datos["concepto"] = {
            "clave": concepto.clave,
            "descripcion": concepto.descripcion,
            "unidad": concepto.unidad,
            "cantidad_fmt": fmt(cantidad),
            "importe_fmt": fmt(mon(mon(detalle_pie.precio_venta) * cantidad)),
        }
    return datos


def _fila_insumo(proyecto: ic.Proyecto, insumo: ic.Insumo,
                 costo_mo: Decimal) -> dict:
    mon = proyecto.precision.moneda
    recurso = insumo.recurso
    if recurso.es_porcentaje_mo:
        costo_unitario = mon(costo_mo)
    else:
        costo_unitario = mon(recurso.costo_unitario(proyecto))
    total = mon(insumo.cantidad_decimal * costo_unitario)
    fila = {
        "clave": recurso.clave,
        "descripcion": recurso.descripcion,
        "tipo": recurso.tipo.value,
        "unidad": recurso.unidad,
        "cantidad": crudo(insumo.cantidad),
        "costo_fmt": fmt(costo_unitario),
        "costo": crudo(recurso.costo),
        "costo_editable": recurso.tipo in TIPOS_COSTO_EDITABLE
                          and not recurso.es_compuesto
                          and not recurso.formula_costo,
        "total_fmt": fmt(total),
        "es_pct_mo": recurso.es_porcentaje_mo,
        "es_compuesto": recurso.es_compuesto,
        "componentes": [],
    }
    if recurso.es_compuesto:
        fila["componentes"] = [
            {
                "clave": comp.recurso.clave,
                "descripcion": comp.recurso.descripcion,
                "unidad": comp.recurso.unidad,
                "cantidad": crudo(comp.cantidad),
                "costo_fmt": fmt(mon(comp.recurso.costo_unitario(proyecto)))
                             if not comp.recurso.es_porcentaje_mo else "%MO",
            }
            for comp in recurso.componentes
        ]
    return fila


def _datos_pie(proyecto: ic.Proyecto,
               detalle: ic.DetallePrecioVenta) -> dict:
    renglones = []
    for cargo, renglon in zip(proyecto.pie.cargos, detalle.renglones):
        renglones.append({
            "id": cargo.identificador,
            "nombre": cargo.nombre,
            "porcentaje": crudo(cargo.porcentaje),
            "base": cargo.base.value,
            "formula": cargo.formula or "",
            "incluye_isn": cargo.incluye_isn,
            "base_fmt": fmt(renglon.base),
            "importe_fmt": fmt(renglon.importe),
        })
    return {
        "modo": proyecto.pie.modo.value,
        "costo_directo_fmt": fmt(detalle.costo_directo),
        "precio_venta_fmt": fmt(detalle.precio_venta),
        "factor": f"{detalle.factor_sobrecosto:.4f}",
        "renglones": renglones,
    }


# ------------------------------------------------------------------ gantt
DIA_PX = 7  # ancho de un día natural en píxeles


def datos_gantt(proyecto: ic.Proyecto) -> Optional[dict]:
    """Barras del programa alineables a las filas de la hoja.

    Devuelve None si no hay actividades programadas.
    """
    programa = proyecto.programa
    if not programa.actividades:
        return None
    calendario = programa.calendario

    rangos: List[Tuple[ic.Actividad, dt.date, dt.date]] = []
    for actividad in programa.actividades:
        rangos.append((actividad,
                       actividad.fecha_inicio(calendario),
                       actividad.fecha_fin(calendario)))
    inicio_global = min(r[1] for r in rangos)
    fin_global = max(r[2] for r in rangos)
    total_dias = (fin_global - inicio_global).days + 1

    criticas = {a for a in programa.actividades_criticas()}

    barras: Dict[str, List[dict]] = {}
    extremos: Dict[str, Tuple[dt.date, dt.date]] = {}
    for actividad, ini, fin in rangos:
        clave = actividad.concepto.clave
        for segmento in actividad.segmentos:
            seg_ini, seg_fin = segmento.fechas(calendario)
            barras.setdefault(f"c:{clave}", []).append({
                "off": (seg_ini - inicio_global).days,
                "dias": (seg_fin - seg_ini).days + 1,
                "critica": actividad in criticas,
                "titulo": f"{clave}: {seg_ini} → {seg_fin}"
                          f" ({segmento.duracion_laborable} días lab.)",
            })
        previo = extremos.get(clave)
        extremos[clave] = (min(ini, previo[0]) if previo else ini,
                           max(fin, previo[1]) if previo else fin)

    # Barras resumen por agrupador: abarcan a sus conceptos descendientes.
    def rango_agrupador(nodo: Agrupador) -> Optional[Tuple[dt.date, dt.date]]:
        fechas = [extremos[c.clave] for c in nodo.iter_conceptos()
                  if c.clave in extremos]
        if not fechas:
            return None
        return min(f[0] for f in fechas), max(f[1] for f in fechas)

    def visitar(nodo: Agrupador, ruta: str) -> None:
        for hijo in nodo.hijos:
            if isinstance(hijo, Agrupador):
                ruta_hijo = f"{ruta}/{hijo.clave}" if ruta else hijo.clave
                rango = rango_agrupador(hijo)
                if rango is not None:
                    barras[f"a:{ruta_hijo}"] = [{
                        "off": (rango[0] - inicio_global).days,
                        "dias": (rango[1] - rango[0]).days + 1,
                        "resumen": True,
                        "titulo": f"{hijo.descripcion}: {rango[0]} → {rango[1]}",
                    }]
                visitar(hijo, ruta_hijo)

    visitar(proyecto.raiz, "")

    return {
        "inicio": inicio_global.isoformat(),
        "fin": fin_global.isoformat(),
        "total_dias": total_dias,
        "ancho_px": max(480, total_dias * DIA_PX),
        "meses": _meses(inicio_global, fin_global, total_dias),
        "barras": barras,
    }


_NOMBRES_MES = ["ene", "feb", "mar", "abr", "may", "jun",
                "jul", "ago", "sep", "oct", "nov", "dic"]


def _meses(inicio: dt.date, fin: dt.date, total_dias: int) -> List[dict]:
    meses = []
    cursor = dt.date(inicio.year, inicio.month, 1)
    while cursor <= fin:
        if cursor.month == 12:
            siguiente = dt.date(cursor.year + 1, 1, 1)
        else:
            siguiente = dt.date(cursor.year, cursor.month + 1, 1)
        desde = max(cursor, inicio)
        hasta = min(siguiente - dt.timedelta(days=1), fin)
        meses.append({
            "etiqueta": f"{_NOMBRES_MES[cursor.month - 1]} {cursor.year}",
            "off": (desde - inicio).days,
            "dias": (hasta - desde).days + 1,
        })
        cursor = siguiente
    return meses
