"""Cargo por Financiamiento — video 32 (Art. 183/184 RLOPSRM).

Modela el flujo de caja del contratista: egresos según el programa de
obra contra ingresos (anticipos y estimaciones cobradas con desfase),
aplicando intereses sobre los saldos.

- RF-02 video 32: periodos de estimación y desfase de la primera
  estimación cobrada.
- RF-03 video 32: tasa pasiva (a favor) y activa (a pagar).
- RF-04 video 32: anticipo sobre el total de la obra o sobre el monto de
  materiales, con entregas parciales por periodo.
- RF-05 video 32: "Calcular" inyecta el porcentaje resultante al pie de
  precios.
- RNF-01 video 32: precondición — se requiere el programa de egresos
  (derivado del programa de obra y la explosión de insumos).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Sequence, Tuple

from .pie_precios import PiePrecios
from .precision import ConfiguracionPrecision, D, Numero, redondear


class BaseAnticipo(enum.Enum):
    TOTAL_OBRA = "Sobre el costo total de la obra"
    MATERIALES = "Sobre el monto de materiales"


@dataclass
class RenglonFlujo:
    periodo: int
    egreso: Decimal
    ingreso: Decimal
    flujo: Decimal
    saldo: Decimal
    interes: Decimal


@dataclass
class ResultadoFinanciamiento:
    renglones: List[RenglonFlujo]
    total_egresos: Decimal
    total_intereses: Decimal
    porcentaje_financiamiento: Decimal


class ErrorPrecondicion(RuntimeError):
    """No hay programa de egresos: el programa de obra y la explosión de
    insumos deben generarse antes (RNF-01 video 32)."""


class CalculoFinanciamiento:
    def __init__(self,
                 tasa_activa_anual_pct: Numero = 0,
                 tasa_pasiva_anual_pct: Numero = 0,
                 periodos_por_anio: int = 12,
                 desfase_cobro_periodos: int = 1,
                 anticipo_pct: Numero = 0,
                 base_anticipo: BaseAnticipo = BaseAnticipo.TOTAL_OBRA,
                 monto_materiales: Numero = 0,
                 anticipos_parciales: Optional[Sequence[Tuple[int, Numero]]] = None,
                 precision: ConfiguracionPrecision | None = None) -> None:
        self.tasa_activa_anual_pct = D(tasa_activa_anual_pct)
        self.tasa_pasiva_anual_pct = D(tasa_pasiva_anual_pct)
        self.periodos_por_anio = periodos_por_anio
        self.desfase_cobro_periodos = desfase_cobro_periodos
        self.anticipo_pct = D(anticipo_pct)
        self.base_anticipo = base_anticipo
        self.monto_materiales = D(monto_materiales)
        self.anticipos_parciales = list(anticipos_parciales or [])
        self.precision = precision or ConfiguracionPrecision()

    # ------------------------------------------------------------------
    def _monto_anticipo(self, total_obra: Decimal) -> Decimal:
        base = (self.monto_materiales
                if self.base_anticipo == BaseAnticipo.MATERIALES else total_obra)
        return base * self.anticipo_pct / 100

    def _ingresos(self, egresos: Sequence[Decimal]) -> List[Decimal]:
        """Construye el programa de ingresos: anticipo(s) + estimaciones
        cobradas con desfase, amortizando el anticipo en cada estimación."""
        total_obra = sum(egresos, Decimal(0))
        anticipo_total = self._monto_anticipo(total_obra)
        n = len(egresos) + self.desfase_cobro_periodos
        ingresos = [Decimal(0)] * n
        # Entrega del anticipo: total al inicio o parcial por periodos
        # (RF-04 video 32).
        if self.anticipos_parciales:
            for periodo, pct in self.anticipos_parciales:
                ingresos[periodo] += anticipo_total * D(pct) / 100
        else:
            ingresos[0] += anticipo_total
        # Estimaciones: el trabajo del periodo k se cobra en k+desfase,
        # neto de la amortización proporcional del anticipo.
        proporcion_amortizacion = (
            anticipo_total / total_obra if total_obra else Decimal(0))
        for k, egreso in enumerate(egresos):
            cobro = D(egreso) * (Decimal(1) - proporcion_amortizacion)
            ingresos[k + self.desfase_cobro_periodos] += cobro
        return ingresos

    def calcular(self, egresos_por_periodo: Sequence[Numero]) -> ResultadoFinanciamiento:
        egresos = [D(e) for e in egresos_por_periodo]
        if not egresos or all(e == 0 for e in egresos):
            raise ErrorPrecondicion(
                "Se requiere el programa de egresos (programa de obra y "
                "explosión de insumos) antes de calcular el financiamiento.")
        ingresos = self._ingresos(egresos)
        egresos += [Decimal(0)] * (len(ingresos) - len(egresos))

        tasa_activa = self.tasa_activa_anual_pct / 100 / self.periodos_por_anio
        tasa_pasiva = self.tasa_pasiva_anual_pct / 100 / self.periodos_por_anio

        renglones: List[RenglonFlujo] = []
        saldo = Decimal(0)
        total_intereses = Decimal(0)
        for periodo, (egreso, ingreso) in enumerate(zip(egresos, ingresos), start=1):
            flujo = ingreso - egreso
            saldo += flujo
            tasa = tasa_pasiva if saldo >= 0 else tasa_activa
            interes = saldo * tasa  # negativo = costo financiero
            total_intereses += interes
            renglones.append(RenglonFlujo(
                periodo=periodo,
                egreso=self.precision.moneda(egreso),
                ingreso=self.precision.moneda(ingreso),
                flujo=self.precision.moneda(flujo),
                saldo=self.precision.moneda(saldo),
                interes=self.precision.moneda(interes),
            ))
        total_egresos = sum(egresos, Decimal(0))
        # Costo (positivo) cuando los intereses netos son en contra.
        porcentaje = (-total_intereses / total_egresos * 100
                      if total_egresos else Decimal(0))
        return ResultadoFinanciamiento(
            renglones=renglones,
            total_egresos=self.precision.moneda(total_egresos),
            total_intereses=self.precision.moneda(total_intereses),
            porcentaje_financiamiento=redondear(porcentaje, self.precision.porcentajes),
        )

    def transferir_a(self, pie: PiePrecios, egresos_por_periodo: Sequence[Numero],
                     identificador: str = "FIN") -> Decimal:
        """RF-05 video 32: botón "Calcular" — inyecta el porcentaje final
        en el pie de precios unitarios."""
        resultado = self.calcular(egresos_por_periodo)
        pie.asignar_porcentaje(identificador, resultado.porcentaje_financiamiento)
        return resultado.porcentaje_financiamiento
