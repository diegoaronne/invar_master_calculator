"""Estado de una sesión demo: el proyecto más la configuración de
sobrecostos capturada en el wizard.

El motor (`invar_calculator`) no guarda los objetos de cálculo de
indirectos/financiamiento/utilidad dentro del proyecto — solo su efecto
en el pie de precios. Para que el wizard pueda editarlos y re-aplicarlos,
esta capa los conserva junto al proyecto en la sesión.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import invar_calculator as ic


@dataclass
class EstadoSesion:
    proyecto: ic.Proyecto
    indirectos: Optional[ic.CalculoIndirectos] = None
    financiamiento: Optional[ic.CalculoFinanciamiento] = None
    utilidad: Optional[ic.CalculoUtilidad] = None
    adicionales_pct: Optional[str] = None
    resultado_financiamiento: Optional[object] = None
    avisos: List[str] = field(default_factory=list)

    def aplicar_sobrecostos(self) -> List[str]:
        """Re-aplica al pie de precios los cálculos configurados, en el
        orden normativo: indirectos → financiamiento → utilidad →
        cargos adicionales. Devuelve avisos no fatales."""
        avisos: List[str] = []
        p = self.proyecto

        if self.indirectos is not None:
            self.indirectos.transferir_a(
                p.pie, p.costo_directo_total(), p.fsr_factor)

        if self.financiamiento is not None:
            # RNF-01 video 32: el financiamiento requiere un programa de
            # egresos; sin actividades programadas no hay flujo de caja.
            flujo = p.programa.programa_montos(
                ic.EscalaTiempo.MES, p, con_sobrecostos=False)
            egresos = list(flujo.values())
            if not any(egresos):
                self.resultado_financiamiento = None
                avisos.append(
                    "Financiamiento no aplicado: primero captura el "
                    "programa de obra (paso 5) para conocer los egresos.")
            else:
                self.financiamiento.transferir_a(p.pie, egresos)
                self.resultado_financiamiento = (
                    self.financiamiento.calcular(egresos))

        if self.utilidad is not None:
            self.utilidad.transferir_a_presupuesto(p.pie)

        if self.adicionales_pct is not None:
            p.pie.asignar_porcentaje("ADIC", self.adicionales_pct)

        avisos.extend(p.validar())
        self.avisos = avisos
        return avisos
