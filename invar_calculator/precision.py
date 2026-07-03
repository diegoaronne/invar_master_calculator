"""Precisión numérica del sistema.

Todo el motor opera con ``decimal.Decimal`` para evitar errores de punto
flotante en etapas críticas del presupuesto (RNF: "Precisión Matemática",
"Flexibilidad de Entrada de Datos"). El número de decimales es configurable
por ámbito (matrices, FSR, costo horario, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Union

Numero = Union[int, float, str, Decimal]


def D(valor: Numero) -> Decimal:
    """Convierte cualquier entrada numérica a Decimal de forma segura."""
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, float):
        # repr() conserva el valor "visible" evitando la basura binaria.
        return Decimal(repr(valor))
    return Decimal(str(valor))


def redondear(valor: Numero, decimales: int) -> Decimal:
    exp = Decimal(1).scaleb(-decimales) if decimales > 0 else Decimal(1)
    return D(valor).quantize(exp, rounding=ROUND_HALF_UP)


@dataclass
class ConfiguracionPrecision:
    """Decimales por ámbito de cálculo (configurables por proyecto).

    Cumple RF-05 (video 1: decimales para matrices, factores de equipo y
    costos horarios) y RNF-03 (video 21: p. ej. 5 decimales para el FSR).
    """

    matrices: int = 2
    costos: int = 2
    fsr: int = 5
    costo_horario: int = 4
    cantidades: int = 4
    porcentajes: int = 4

    def moneda(self, valor: Numero) -> Decimal:
        return redondear(valor, self.costos)

    def factor(self, valor: Numero) -> Decimal:
        return redondear(valor, self.fsr)
