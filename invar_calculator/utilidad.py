"""Cargo por Utilidad — video 33 (Art. 188 RLOPSRM).

A partir de la utilidad neta deseada deduce la utilidad bruta que debe
cargarse al presupuesto para que, tras ISR y PTU, la empresa reciba el
margen esperado:

    UB = UN / (1 - ISR - PTU)

- RF-01 video 33: ISR y PTU configurables por régimen y año fiscal.
- RF-03 video 33: captura de la utilidad neta objetivo.
- RF-05 video 33 / RNF-01: transferencia del factor al pie de precios,
  donde se aplica sobre CD + CI + CF (base acumulable).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict

from .pie_precios import PiePrecios
from .precision import ConfiguracionPrecision, D, Numero


@dataclass
class CalculoUtilidad:
    isr_pct: Numero = 30
    ptu_pct: Numero = 10
    utilidad_neta_pct: Numero = 0
    precision: ConfiguracionPrecision = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.precision is None:
            self.precision = ConfiguracionPrecision()

    def utilidad_bruta_pct(self) -> Decimal:
        """Porcentaje bruto necesario para proteger la utilidad neta."""
        isr = D(self.isr_pct) / 100
        ptu = D(self.ptu_pct) / 100
        gravamen = isr + ptu
        if gravamen >= 1:
            raise ValueError("ISR + PTU no puede ser 100% o más.")
        bruta = D(self.utilidad_neta_pct) / (Decimal(1) - gravamen)
        from .precision import redondear
        return redondear(bruta, self.precision.porcentajes)

    def hoja_calculo(self) -> Dict[str, Decimal]:
        """Desglose estilo hoja de cálculo (RF-02 video 33)."""
        bruta = self.utilidad_bruta_pct()
        isr = bruta * D(self.isr_pct) / 100
        ptu = bruta * D(self.ptu_pct) / 100
        from .precision import redondear
        r = lambda v: redondear(v, self.precision.porcentajes)
        return {
            "Utilidad neta deseada (%)": r(D(self.utilidad_neta_pct)),
            "ISR sobre utilidad (%)": r(isr),
            "PTU sobre utilidad (%)": r(ptu),
            "Utilidad bruta requerida (%)": bruta,
        }

    def transferir_a_presupuesto(self, pie: PiePrecios,
                                 identificador: str = "UTIL") -> Decimal:
        """RF-05 video 33: inyección atómica al pie de precios."""
        bruta = self.utilidad_bruta_pct()
        pie.asignar_porcentaje(identificador, bruta)
        return bruta
