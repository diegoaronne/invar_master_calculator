"""Números Generadores — video 10.

Cuantificación manual de conceptos: cada línea de medición registra una
referencia física ("Eje 1", "Tramo A-B") y sus dimensiones; la cantidad
del concepto se deriva de la suma de las líneas.

- RF-01: columnas referencia, largo, ancho, alto y factor/piezas.
- RF-02: cantidad = largo × ancho × alto × piezas (dimensiones omitidas
  cuentan como 1).
- RF-03: trazabilidad de la medición mediante la referencia.
- RF-04: cuantificación híbrida — también acepta cantidades ya
  calculadas externamente.
- RNF-02: la cantidad del concepto se actualiza automáticamente
  (``Concepto.cantidad_efectiva`` consulta al generador).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from .precision import ConfiguracionPrecision, D, Numero, redondear


@dataclass
class LineaGenerador:
    referencia: str = ""
    largo: Numero | None = None
    ancho: Numero | None = None
    alto: Numero | None = None
    piezas: Numero = 1
    cantidad_directa: Numero | None = None  # RF-04: dato externo ya calculado

    def cantidad(self) -> Decimal:
        if self.cantidad_directa is not None:
            return D(self.cantidad_directa)
        producto = D(self.piezas)
        for dimension in (self.largo, self.ancho, self.alto):
            if dimension is not None:
                producto *= D(dimension)
        return producto


class NumerosGeneradores:
    def __init__(self, precision: ConfiguracionPrecision | None = None) -> None:
        self.lineas: List[LineaGenerador] = []
        self.precision = precision or ConfiguracionPrecision()

    def agregar(self, referencia: str = "", largo: Numero | None = None,
                ancho: Numero | None = None, alto: Numero | None = None,
                piezas: Numero = 1,
                cantidad_directa: Numero | None = None) -> LineaGenerador:
        linea = LineaGenerador(referencia, largo, ancho, alto, piezas, cantidad_directa)
        self.lineas.append(linea)
        return linea

    def cantidad_total(self) -> Decimal:
        total = sum((l.cantidad() for l in self.lineas), Decimal(0))
        return redondear(total, self.precision.cantidades)
