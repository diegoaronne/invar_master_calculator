"""Convierte objetos `Tabla` del motor (invar_calculator.reportes) en HTML.

No modifica invar_calculator: consume únicamente los atributos públicos ya
expuestos (`Tabla.titulo`, `Tabla.columnas`, `Tabla.filas`,
`Columna.imprimible`). Esto mantiene la capa de cálculo/reportes intacta y
100% cubierta por los tests existentes.
"""
from __future__ import annotations

import csv
import io
from html import escape
from typing import Callable, Iterable, List, Optional


def tabla_a_html(tabla, solo_imprimibles: bool = True,
                 enlace_csv: Optional[str] = None) -> str:
    """Renderiza una Tabla como <table> HTML.

    `solo_imprimibles=True` respeta el flag Columna.imprimible (RF-04) —
    útil para la vista cliente, que no debe ver columnas marcadas como
    internas aunque la tabla en sí se muestre.
    """
    indices = [i for i, c in enumerate(tabla.columnas)
               if c.imprimible or not solo_imprimibles]
    encabezados = [tabla.columnas[i].titulo for i in indices]

    thead = "".join(f"<th>{escape(h)}</th>" for h in encabezados)
    filas_html = []
    for fila in tabla.filas:
        celdas = "".join(f"<td>{escape(str(fila[i]))}</td>" for i in indices)
        filas_html.append(f"<tr>{celdas}</tr>")

    boton_csv = ""
    if enlace_csv:
        boton_csv = (f'<a class="btn-csv no-imprimir" href="{escape(enlace_csv)}"'
                     f' download>CSV</a>')

    return (
        f'<section class="tabla-reporte">'
        f'<div class="tabla-encabezado"><h3>{escape(tabla.titulo)}</h3>'
        f'{boton_csv}</div>'
        f'<table><thead><tr>{thead}</tr></thead>'
        f'<tbody>{"".join(filas_html)}</tbody></table>'
        f'</section>'
    )


class TablaFiltrada:
    """Vista de solo lectura de una Tabla con filas filtradas.

    Permite ocultar renglones sensibles (p. ej. los cargos del pie dentro
    del APU en vista cliente) sin tocar la Tabla original del motor.
    """

    def __init__(self, tabla, conservar: Callable[[List[str]], bool],
                 titulo: Optional[str] = None) -> None:
        self.titulo = titulo or tabla.titulo
        self.columnas = tabla.columnas
        self.filas = [f for f in tabla.filas if conservar(f)]

    def a_csv(self, ruta=None, solo_imprimibles: bool = True) -> str:
        indices = [i for i, c in enumerate(self.columnas)
                   if c.imprimible or not solo_imprimibles]
        buffer = io.StringIO()
        escritor = csv.writer(buffer)
        escritor.writerow([self.columnas[i].titulo for i in indices])
        for fila in self.filas:
            escritor.writerow([fila[i] for i in indices])
        return buffer.getvalue()


# Prefijos de títulos de tabla que NUNCA deben mostrarse en la vista
# cliente (sección 7 del brief: sin FSR, pie de precios, financiamiento,
# indirectos ni explosión por costo). Ajustar junto con Diego.
TABLAS_OCULTAS_EN_CLIENTE = (
    "Factor de Salario Real",
    "Pie de precios unitarios",
    "Financiamiento",
    "Explosión de insumos",
    "Programa de suministros",
)


def visible_para_cliente(tabla) -> bool:
    return not tabla.titulo.startswith(TABLAS_OCULTAS_EN_CLIENTE)


def filtrar_para_cliente(tablas: Iterable) -> list:
    return [t for t in tablas if visible_para_cliente(t)]


def presupuesto_para_cliente(tabla) -> TablaFiltrada:
    """El cliente ve el presupuesto sin la fila de COSTO DIRECTO, que
    revelaría el margen al compararla contra el precio de venta."""
    return TablaFiltrada(
        tabla, lambda fila: fila[1].strip() != "COSTO DIRECTO")


def apu_para_cliente(tabla) -> TablaFiltrada:
    """APU sin desglose de márgenes: se conservan los insumos y el precio
    final, y se ocultan el costo directo y los cargos del pie (renglones
    con clave vacía distintos del precio de venta)."""
    return TablaFiltrada(
        tabla,
        lambda fila: (fila[0].strip() != ""
                      or fila[1].strip() == "PRECIO UNITARIO DE VENTA"))
