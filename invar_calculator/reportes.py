"""Reportes e interoperabilidad — videos 22, 31, 32, 34 y 35.

Genera los entregables en texto tabular (para consola/impresión) y CSV
(interoperable con Excel — RNF-01 video 22, RF-05 video 34):

- Presupuesto jerárquico con filtro de nivel.
- Análisis de Precio Unitario (APU) con pie de precios.
- Reportes "Factor PS" y "FSR" (RF-05 video 21).
- Explosión de insumos y programa de suministros.
- Flujo de financiamiento en formato horizontal o vertical (RF-01 v32).

Las columnas soportan la propiedad "imprimible": visibles para el
cálculo pero excluibles del reporte final (RF-04 / RNF-02 video 34).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Set

from .explosion import ExplosionInsumos, ProgramaSuministros
from .financiamiento import ResultadoFinanciamiento
from .modelos import Agrupador, Concepto, TipoRecurso
from .programa import EscalaTiempo
from .proyecto import Proyecto


@dataclass
class Columna:
    titulo: str
    imprimible: bool = True  # RF-04 video 34


class Tabla:
    """Tabla imprimible/exportable con control por columna."""

    def __init__(self, titulo: str, columnas: Sequence[Columna | str]) -> None:
        self.titulo = titulo
        self.columnas = [c if isinstance(c, Columna) else Columna(c)
                         for c in columnas]
        self.filas: List[List[str]] = []

    def agregar_fila(self, *valores: object) -> None:
        if len(valores) != len(self.columnas):
            raise ValueError("La fila no coincide con las columnas.")
        self.filas.append([_formato(v) for v in valores])

    def _indices_imprimibles(self, solo_imprimibles: bool) -> List[int]:
        return [i for i, c in enumerate(self.columnas)
                if c.imprimible or not solo_imprimibles]

    def render(self, solo_imprimibles: bool = True) -> str:
        indices = self._indices_imprimibles(solo_imprimibles)
        encabezados = [self.columnas[i].titulo for i in indices]
        filas = [[fila[i] for i in indices] for fila in self.filas]
        anchos = [max(len(encabezados[j]),
                      *(len(f[j]) for f in filas)) if filas else len(encabezados[j])
                  for j in range(len(encabezados))]
        linea_sep = "-+-".join("-" * a for a in anchos)
        out = [self.titulo, "=" * len(self.titulo)]
        out.append(" | ".join(e.ljust(a) for e, a in zip(encabezados, anchos)))
        out.append(linea_sep)
        for fila in filas:
            out.append(" | ".join(v.ljust(a) for v, a in zip(fila, anchos)))
        return "\n".join(out)

    def a_csv(self, ruta: str | None = None,
              solo_imprimibles: bool = True) -> str:
        """Exportación CSV (interoperable con Excel/Word)."""
        indices = self._indices_imprimibles(solo_imprimibles)
        buffer = io.StringIO()
        escritor = csv.writer(buffer)
        escritor.writerow([self.columnas[i].titulo for i in indices])
        for fila in self.filas:
            escritor.writerow([fila[i] for i in indices])
        contenido = buffer.getvalue()
        if ruta:
            with open(ruta, "w", newline="", encoding="utf-8") as archivo:
                archivo.write(contenido)
        return contenido


def _formato(valor: object) -> str:
    if isinstance(valor, Decimal):
        return f"{valor:,f}"
    return "" if valor is None else str(valor)


# ----------------------------------------------------------------------
def reporte_presupuesto(proyecto: Proyecto, nivel_maximo: int | None = None,
                        con_sobrecostos: bool = True) -> Tabla:
    """Catálogo de conceptos jerárquico (RF-04 video 4, RF-06 video 5)."""
    tabla = Tabla(f"Presupuesto — {proyecto.nombre}",
                  ["Clave", "Descripción", "Unidad", "Cantidad",
                   "P. Unitario", "Importe"])
    for nivel, nodo in proyecto.raiz.iter_nodos(nivel_maximo):
        sangria = "  " * (nivel - 1)
        if isinstance(nodo, Agrupador):
            tabla.agregar_fila(
                sangria + (nodo.clave or "—"), sangria + nodo.descripcion,
                "", "", "", nodo.importe(proyecto, con_sobrecostos))
        else:
            pu = proyecto.precision.moneda(nodo.costo_directo_unitario(proyecto))
            if con_sobrecostos:
                pu = proyecto.precision.moneda(proyecto.precio_venta(pu))
            tabla.agregar_fila(
                sangria + nodo.clave, sangria + nodo.descripcion, nodo.unidad,
                nodo.cantidad_efectiva, pu,
                proyecto.precision.moneda(pu * nodo.cantidad_efectiva))
    resumen = proyecto.recalcular()
    tabla.agregar_fila("", "COSTO DIRECTO", "", "", "", resumen.costo_directo)
    tabla.agregar_fila("", "PRECIO DE VENTA", "", "", "", resumen.precio_venta)
    tabla.agregar_fila("", f"IVA ({proyecto.iva_pct}%)", "", "", "", resumen.iva)
    tabla.agregar_fila("", "TOTAL CON IVA", "", "", "", resumen.total_con_iva)
    return tabla


def reporte_apu(proyecto: Proyecto, concepto: Concepto) -> Tabla:
    """Análisis de precio unitario: matriz + pie de precios (video 12)."""
    tabla = Tabla(f"APU {concepto.clave} — {concepto.descripcion}",
                  ["Clave", "Descripción", "Tipo", "Unidad", "Cantidad",
                   "Costo unitario", "Importe"])
    matriz = concepto.matriz
    if matriz is None:
        return tabla
    costo_mo = sum(
        (i.cantidad_decimal * i.recurso.costo_unitario(proyecto)
         for i in matriz.insumos if i.recurso.tipo == TipoRecurso.MANO_OBRA),
        Decimal(0))
    for insumo in matriz.insumos:
        recurso = insumo.recurso
        if recurso.es_porcentaje_mo:
            costo_unitario = proyecto.precision.moneda(costo_mo)
        else:
            costo_unitario = recurso.costo_unitario(proyecto)
        importe = proyecto.precision.moneda(
            insumo.cantidad_decimal * costo_unitario)
        tabla.agregar_fila(recurso.clave, recurso.descripcion,
                           recurso.tipo.value, recurso.unidad,
                           insumo.cantidad_decimal, costo_unitario, importe)
    detalle = proyecto.pie.aplicar(matriz.costo_unitario(proyecto))
    tabla.agregar_fila("", "COSTO DIRECTO", "", "", "", "",
                       detalle.costo_directo)
    for renglon in detalle.renglones:
        tabla.agregar_fila("", renglon.nombre, "", "",
                           f"{renglon.porcentaje}%", renglon.base,
                           renglon.importe)
    tabla.agregar_fila("", "PRECIO UNITARIO DE VENTA", "", "", "", "",
                       detalle.precio_venta)
    return tabla


def reporte_fsr(proyecto: Proyecto, salario_base) -> Tabla:
    """Reportes "Factor PS" y "FSR" listos para impresión (RF-05 v21)."""
    tabla = Tabla("Factor de Salario Real", ["Concepto", "Valor"])
    for nombre, valor in proyecto.hoja_fsr.reporte_factor_ps(salario_base).items():
        tabla.agregar_fila(nombre, valor)
    for nombre, valor in proyecto.hoja_fsr.reporte_fsr(salario_base).items():
        tabla.agregar_fila(nombre, valor)
    return tabla


def reporte_explosion(proyecto: Proyecto,
                      tipos: Optional[Set[TipoRecurso]] = None,
                      desglosar_equipo: bool = False) -> Tabla:
    """Explosión de insumos (videos 22/28)."""
    explosion = ExplosionInsumos(proyecto, tipos, desglosar_equipo)
    lineas = explosion.generar(proyecto.iter_conceptos())
    tabla = Tabla("Explosión de insumos",
                  ["Clave", "Descripción", "Tipo", "Unidad",
                   "Cantidad", "Importe"])
    total = Decimal(0)
    for linea in lineas.values():
        importe = proyecto.precision.moneda(linea.importe)
        total += importe
        tabla.agregar_fila(linea.clave, linea.descripcion, linea.tipo,
                           linea.unidad,
                           proyecto.precision.factor(linea.cantidad), importe)
    tabla.agregar_fila("", "TOTAL", "", "", "", proyecto.precision.moneda(total))
    return tabla


def reporte_suministros(proyecto: Proyecto, escala: EscalaTiempo,
                        por: str = "cantidad",
                        tipos: Optional[Set[TipoRecurso]] = None,
                        desglosar_equipo: bool = False) -> Tabla:
    """Programa de suministros por periodo (RF-04/RF-05 video 22)."""
    suministros = ProgramaSuministros(proyecto, proyecto.programa, tipos,
                                      desglosar_equipo)
    datos = suministros.generar(escala, por)
    periodos = sorted({p for series in datos.values() for p in series})
    tabla = Tabla(f"Programa de suministros ({por} por {escala.value.lower()})",
                  ["Clave"] + periodos + ["Total"])
    for clave, series in datos.items():
        valores = [proyecto.precision.factor(series.get(p, Decimal(0)))
                   for p in periodos]
        total = proyecto.precision.factor(sum(series.values(), Decimal(0)))
        tabla.agregar_fila(clave, *valores, total)
    return tabla


def reporte_financiamiento(resultado: ResultadoFinanciamiento,
                           formato: str = "horizontal") -> Tabla:
    """Análisis de financiamiento en formato horizontal (periodos como
    columnas) o vertical (periodos como filas) — RF-01 video 32."""
    if formato == "vertical":
        tabla = Tabla("Financiamiento (formato vertical)",
                      ["Periodo", "Egresos", "Ingresos", "Flujo",
                       "Saldo", "Interés"])
        for r in resultado.renglones:
            tabla.agregar_fila(r.periodo, r.egreso, r.ingreso, r.flujo,
                               r.saldo, r.interes)
        tabla.agregar_fila("Total", resultado.total_egresos, "", "", "",
                           resultado.total_intereses)
        tabla.agregar_fila("% Financiamiento",
                           resultado.porcentaje_financiamiento, "", "", "", "")
        return tabla
    if formato != "horizontal":
        raise ValueError("Formato no soportado: use 'horizontal' o 'vertical'.")
    periodos = [str(r.periodo) for r in resultado.renglones]
    tabla = Tabla("Financiamiento (formato horizontal)",
                  ["Concepto"] + periodos + ["Total"])
    tabla.agregar_fila("Egresos", *[r.egreso for r in resultado.renglones],
                       resultado.total_egresos)
    tabla.agregar_fila("Ingresos", *[r.ingreso for r in resultado.renglones], "")
    tabla.agregar_fila("Flujo", *[r.flujo for r in resultado.renglones], "")
    tabla.agregar_fila("Saldo", *[r.saldo for r in resultado.renglones], "")
    tabla.agregar_fila("Interés", *[r.interes for r in resultado.renglones],
                       resultado.total_intereses)
    return tabla


def reporte_pie_precios(proyecto: Proyecto, costo_directo=None) -> Tabla:
    """Resumen del pie de precios sobre el costo directo del proyecto."""
    cd = (proyecto.costo_directo_total()
          if costo_directo is None else costo_directo)
    detalle = proyecto.pie.aplicar(cd)
    tabla = Tabla("Pie de precios unitarios",
                  ["Cargo", "% aplicado", "Base", "Importe"])
    tabla.agregar_fila("Costo directo", "", "", detalle.costo_directo)
    for renglon in detalle.renglones:
        tabla.agregar_fila(renglon.nombre, renglon.porcentaje, renglon.base,
                           renglon.importe)
    tabla.agregar_fila("PRECIO DE VENTA", "", "", detalle.precio_venta)
    return tabla
