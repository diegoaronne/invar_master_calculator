"""Gestión multimoneda del proyecto.

Cumple RF-02 (video 2): moneda base, nacional y extranjera con nombre,
símbolo, abreviación, fracción monetaria y tipo de cambio independiente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict

from .precision import D, Numero


@dataclass
class Moneda:
    abreviacion: str
    nombre: str = ""
    simbolo: str = "$"
    fraccion: str = "centavos"
    tipo_cambio: Decimal = Decimal(1)  # unidades de moneda base por 1 unidad de esta moneda

    def __post_init__(self) -> None:
        self.tipo_cambio = D(self.tipo_cambio)


class SistemaMonedas:
    """Registro de monedas del proyecto y conversión a moneda base."""

    def __init__(self, base: Moneda | None = None) -> None:
        self.base = base or Moneda("MXN", "Peso mexicano", "$")
        self.base.tipo_cambio = Decimal(1)
        self._monedas: Dict[str, Moneda] = {self.base.abreviacion: self.base}
        self.multimoneda = False

    def registrar(self, moneda: Moneda) -> Moneda:
        self._monedas[moneda.abreviacion] = moneda
        if moneda.abreviacion != self.base.abreviacion:
            self.multimoneda = True
        return moneda

    def obtener(self, abreviacion: str) -> Moneda:
        try:
            return self._monedas[abreviacion]
        except KeyError:
            raise KeyError(f"Moneda no registrada: {abreviacion!r}") from None

    def a_base(self, importe: Numero, abreviacion: str | None = None) -> Decimal:
        """Convierte un importe expresado en `abreviacion` a la moneda base."""
        if abreviacion is None or abreviacion == self.base.abreviacion:
            return D(importe)
        return D(importe) * self.obtener(abreviacion).tipo_cambio
