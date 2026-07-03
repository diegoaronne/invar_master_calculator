"""Explosión de Insumos y Programa de Suministros — videos 22 y 28.

Procesa el presupuesto para desglosar los recursos básicos (materiales,
mano de obra, equipo, etc.) que exige la ejecución:

- RF-01 video 22: explosión de insumos básicos desde las matrices.
- RF-02 video 22: filtros por tipo de recurso.
- RF-03 video 22: desglose opcional del costo horario de la maquinaria
  (cargos fijos, consumos, operación).
- RF-04/RF-05 video 22: suministros por periodo (escalas de tiempo) en
  cantidades o montos.
- RF-04 video 13: recursos "indivisibles" se redondean a enteros hacia
  arriba en la explosión.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING
from typing import Dict, Iterable, List, Optional, Set

from .modelos import Concepto, ContextoCalculo, Recurso, TipoRecurso
from .precision import D, Numero
from .programa import EscalaTiempo, ProgramaObra


@dataclass
class LineaExplosion:
    clave: str
    descripcion: str
    unidad: str
    tipo: str
    cantidad: Decimal = Decimal(0)
    importe: Decimal = Decimal(0)


class ExplosionInsumos:
    def __init__(self, ctx: ContextoCalculo,
                 tipos: Optional[Set[TipoRecurso]] = None,
                 desglosar_equipo: bool = False) -> None:
        self.ctx = ctx
        self.tipos = tipos  # None = todos (RF-02 video 22)
        self.desglosar_equipo = desglosar_equipo

    # ------------------------------------------------------------------
    def generar(self, conceptos: Iterable[Concepto],
                aplicar_indivisibles: bool = True) -> Dict[str, LineaExplosion]:
        acumulador: Dict[str, LineaExplosion] = {}
        for concepto in conceptos:
            if concepto.matriz is None:
                continue
            self._expandir(concepto.matriz, concepto.cantidad_efectiva, acumulador)
        if aplicar_indivisibles:
            self._aplicar_indivisibles(acumulador)
        return dict(sorted(acumulador.items()))

    def _incluye(self, recurso: Recurso) -> bool:
        return self.tipos is None or recurso.tipo in self.tipos

    def _expandir(self, recurso: Recurso, cantidad: Decimal,
                  acumulador: Dict[str, LineaExplosion]) -> None:
        if recurso.datos_costo_horario is not None:
            self._expandir_equipo(recurso, cantidad, acumulador)
            return
        if recurso.es_compuesto:
            costo_mo = sum(
                (i.cantidad_decimal * i.recurso.costo_unitario(self.ctx)
                 for i in recurso.componentes
                 if i.recurso.tipo == TipoRecurso.MANO_OBRA
                 and not i.recurso.es_porcentaje_mo),
                Decimal(0))
            for insumo in recurso.componentes:
                hijo = insumo.recurso
                cantidad_hija = cantidad * insumo.cantidad_decimal
                if hijo.es_porcentaje_mo:
                    if self._incluye(hijo):
                        self._acumular(hijo, cantidad_hija, cantidad_hija * costo_mo,
                                       acumulador)
                elif hijo.es_compuesto or hijo.datos_costo_horario is not None:
                    self._expandir(hijo, cantidad_hija, acumulador)
                else:
                    if self._incluye(hijo):
                        importe = cantidad_hija * hijo.costo_unitario(self.ctx)
                        self._acumular(hijo, cantidad_hija, importe, acumulador)
            return
        if self._incluye(recurso):
            importe = cantidad * recurso.costo_unitario(self.ctx)
            self._acumular(recurso, cantidad, importe, acumulador)

    def _expandir_equipo(self, recurso: Recurso, horas: Decimal,
                         acumulador: Dict[str, LineaExplosion]) -> None:
        """El equipo se explota como costo horario consolidado o
        desglosado en sus cargos (RF-03 video 22 / RNF-03 video 32)."""
        if not self._incluye(recurso):
            return
        if not self.desglosar_equipo:
            importe = horas * recurso.costo_unitario(self.ctx)
            self._acumular(recurso, horas, importe, acumulador)
            return
        desglose = recurso.datos_costo_horario.desglose(self.ctx.precision)  # type: ignore[attr-defined]
        for grupo, componentes in desglose.items():
            for nombre, costo_hora in componentes.items():
                clave = f"{recurso.clave}.{nombre}"
                linea = acumulador.setdefault(clave, LineaExplosion(
                    clave=clave,
                    descripcion=f"{recurso.descripcion} — {grupo}: {nombre}",
                    unidad="hr",
                    tipo=f"{TipoRecurso.EQUIPO.value} ({grupo})",
                ))
                linea.cantidad += horas
                linea.importe += horas * costo_hora

    def _acumular(self, recurso: Recurso, cantidad: Decimal, importe: Decimal,
                  acumulador: Dict[str, LineaExplosion]) -> None:
        linea = acumulador.setdefault(recurso.clave, LineaExplosion(
            clave=recurso.clave,
            descripcion=recurso.descripcion,
            unidad=recurso.unidad,
            tipo=recurso.tipo.value,
        ))
        linea.cantidad += cantidad
        linea.importe += importe

    def _aplicar_indivisibles(self, acumulador: Dict[str, LineaExplosion]) -> None:
        """RF-04 video 13: los recursos indivisibles se explotan en
        números enteros (redondeo hacia arriba)."""
        for linea in acumulador.values():
            recurso = self._buscar_indivisible(linea.clave)
            if recurso is None:
                continue
            cantidad_entera = linea.cantidad.to_integral_value(rounding=ROUND_CEILING)
            if cantidad_entera != linea.cantidad and linea.cantidad > 0:
                costo_unitario = linea.importe / linea.cantidad
                linea.cantidad = cantidad_entera
                linea.importe = cantidad_entera * costo_unitario

    def _buscar_indivisible(self, clave: str) -> Optional[Recurso]:
        catalogo = getattr(self.ctx, "catalogo", None)
        if catalogo is None or clave not in catalogo:
            return None
        recurso = catalogo.obtener(clave)
        return recurso if recurso.indivisible else None


class ProgramaSuministros:
    """Suministros por periodo: explosión × distribución temporal
    (RF-04/RF-05 video 22, videos 28)."""

    def __init__(self, ctx: ContextoCalculo, programa: ProgramaObra,
                 tipos: Optional[Set[TipoRecurso]] = None,
                 desglosar_equipo: bool = False) -> None:
        self.ctx = ctx
        self.programa = programa
        self.tipos = tipos
        self.desglosar_equipo = desglosar_equipo

    def generar(self, escala: EscalaTiempo,
                por: str = "cantidad") -> Dict[str, Dict[str, Decimal]]:
        """Regresa {clave_insumo: {periodo: cantidad|monto}}.

        ``por`` acepta "cantidad" o "monto" (RF-05 video 22).
        """
        if por not in ("cantidad", "monto"):
            raise ValueError("El parámetro 'por' debe ser 'cantidad' o 'monto'.")
        resultado: Dict[str, Dict[str, Decimal]] = {}
        for actividad in self.programa.actividades:
            concepto = actividad.concepto
            if concepto.matriz is None:
                continue
            # Explosión por unidad de concepto.
            explosion = ExplosionInsumos(
                self.ctx, self.tipos, self.desglosar_equipo)
            por_unidad = explosion.generar(
                [Concepto(clave=concepto.clave, descripcion=concepto.descripcion,
                          unidad=concepto.unidad, cantidad=1,
                          matriz=concepto.matriz)],
                aplicar_indivisibles=False)
            # Distribución temporal de la cantidad del concepto.
            reparto = self.programa.distribuir_actividad(
                actividad, escala, concepto.cantidad_efectiva)
            for clave, linea in por_unidad.items():
                destino = resultado.setdefault(clave, {})
                for etiqueta, cantidad_periodo in reparto.items():
                    valor = (linea.cantidad if por == "cantidad" else linea.importe)
                    destino[etiqueta] = (destino.get(etiqueta, Decimal(0))
                                         + valor * cantidad_periodo)
        return {clave: dict(sorted(periodos.items()))
                for clave, periodos in sorted(resultado.items())}
