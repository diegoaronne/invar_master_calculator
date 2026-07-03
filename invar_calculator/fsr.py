"""Factor de Salario Real (FSR) — video 21 y video 2.

Implementa la fórmula del Art. 190 del Reglamento de la Ley de Obras
Públicas y Servicios Relacionados con las Mismas (México):

    FSR = Ps * (Tp / Tl) + (Tp / Tl)

donde ``Tp`` son los días realmente pagados al año, ``Tl`` los días
realmente laborados y ``Ps`` la fracción que representan las obligaciones
patronales (IMSS, INFONAVIT, prima de riesgo e ISN opcional) respecto al
salario del trabajador.

- RF-01 video 21: variables de entorno (salario mínimo, prima de riesgo,
  año fiscal, ISN).
- RF-02 video 21: calendario laboral (domingos, vacaciones, festivos,
  clima, costumbre, permisos).
- RF-03 video 21: prestaciones de ley con mínimos automáticos y
  personalización.
- RF-04 video 21: aportaciones patronales configurables.
- RNF-01 video 21: el salario mínimo de referencia es el general
  (CDMX/Distrito Federal) conforme a la Ley del Seguro Social.
- RNF-02 video 21: bandera ``incluir_isn`` para prevenir duplicidad con
  los cargos adicionales del pie de precios.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List

from .precision import ConfiguracionPrecision, D, Numero, redondear


@dataclass
class CalendarioLaboralAnual:
    """Días no laborados en el año (RF-02 video 21)."""

    dias_del_anio: Numero = 365
    domingos: Numero = 52
    dias_festivos: Numero = "7.17"  # promedio legal considerando años bisiestos
    dias_vacaciones: Numero = 12    # mínimo LFT 2023+ (personalizable)
    dias_por_clima: Numero = 0
    dias_por_costumbre: Numero = 0
    dias_por_permisos: Numero = 0

    def dias_no_laborados(self) -> Decimal:
        return (D(self.domingos) + D(self.dias_festivos) + D(self.dias_vacaciones)
                + D(self.dias_por_clima) + D(self.dias_por_costumbre)
                + D(self.dias_por_permisos))

    def dias_laborados(self) -> Decimal:
        """Tl: días realmente laborados; alimenta el factor de
        productividad anual."""
        return D(self.dias_del_anio) - self.dias_no_laborados()


@dataclass
class PrestacionesLey:
    """Prestaciones mínimas de ley con opción a superiores (RF-03 v21)."""

    dias_aguinaldo: Numero = 15
    dias_vacaciones: Numero = 12
    prima_vacacional: Numero = "0.25"
    prima_dominical: Numero = "0.25"
    domingos_trabajados: Numero = 0  # solo si la jornada incluye domingos

    def dias_pagados_adicionales(self) -> Decimal:
        return (D(self.dias_aguinaldo)
                + D(self.dias_vacaciones) * D(self.prima_vacacional)
                + D(self.domingos_trabajados) * D(self.prima_dominical))


@dataclass
class CuotaPatronal:
    """Aportación patronal (RF-04 video 21).

    ``base`` indica sobre qué se aplica el porcentaje:
    - "salario": sobre el salario del trabajador (caso general).
    - "smg": sobre el salario mínimo general (cuota fija IMSS, Art. 106).
    """

    nombre: str
    porcentaje: Numero
    base: str = "salario"

    def fraccion(self, salario_base: Decimal, salario_minimo: Decimal) -> Decimal:
        pct = D(self.porcentaje) / Decimal(100)
        if self.base == "smg":
            if salario_base == 0:
                return Decimal(0)
            return pct * salario_minimo / salario_base
        return pct


def cuotas_imss_default(prima_riesgo_pct: Numero = "7.58875") -> List[CuotaPatronal]:
    """Cuotas patronales típicas IMSS/INFONAVIT/SAR (RF-04 video 21).

    Los porcentajes son parametrizables; estos valores corresponden al
    régimen obligatorio mexicano y sirven como plantilla inicial.
    """
    return [
        CuotaPatronal("Enfermedad y maternidad (cuota fija)", "20.40", base="smg"),
        CuotaPatronal("Enfermedad y maternidad (prestaciones en dinero)", "0.70"),
        CuotaPatronal("Gastos médicos pensionados", "1.05"),
        CuotaPatronal("Invalidez y vida", "1.75"),
        CuotaPatronal("Guarderías y prestaciones sociales", "1.00"),
        CuotaPatronal("Retiro (SAR)", "2.00"),
        CuotaPatronal("Cesantía en edad avanzada y vejez", "3.150"),
        CuotaPatronal("INFONAVIT", "5.00"),
        CuotaPatronal("Riesgo de trabajo", prima_riesgo_pct),
    ]


class HojaFSR:
    """Hoja de cálculo del FSR del proyecto (editable — RNF-02 video 2)."""

    def __init__(self,
                 salario_minimo_general: Numero = "278.80",
                 anio_fiscal: int = 2026,
                 prima_riesgo_pct: Numero = "7.58875",
                 isn_pct: Numero = "3.0",
                 incluir_isn: bool = True,
                 calendario: CalendarioLaboralAnual | None = None,
                 prestaciones: PrestacionesLey | None = None,
                 cuotas: List[CuotaPatronal] | None = None,
                 precision: ConfiguracionPrecision | None = None) -> None:
        self.salario_minimo_general = D(salario_minimo_general)
        self.anio_fiscal = anio_fiscal
        self.prima_riesgo_pct = D(prima_riesgo_pct)
        self.isn_pct = D(isn_pct)
        self.incluir_isn = incluir_isn
        self.calendario = calendario or CalendarioLaboralAnual()
        self.prestaciones = prestaciones or PrestacionesLey()
        self.cuotas = cuotas if cuotas is not None else cuotas_imss_default(prima_riesgo_pct)
        self.precision = precision or ConfiguracionPrecision()

    # ------------------------------------------------------------------
    def dias_pagados(self) -> Decimal:
        """Tp = días del año + prestaciones pagadas (aguinaldo, primas)."""
        return D(self.calendario.dias_del_anio) + self.prestaciones.dias_pagados_adicionales()

    def dias_laborados(self) -> Decimal:
        tl = self.calendario.dias_laborados()
        if tl <= 0:
            raise ValueError("El calendario laboral no deja días laborables.")
        return tl

    def factor_prestaciones(self) -> Decimal:
        """Tp/Tl — factor por prestaciones y días efectivamente laborados."""
        return self.dias_pagados() / self.dias_laborados()

    def fraccion_cuotas(self, salario_base: Numero) -> Decimal:
        """Ps: fracción del salario que representan las obligaciones
        patronales para un salario base diario dado."""
        salario = D(salario_base)
        total = Decimal(0)
        for cuota in self.cuotas:
            total += cuota.fraccion(salario, self.salario_minimo_general)
        if self.incluir_isn:
            total += self.isn_pct / Decimal(100)
        return total

    def factor(self, salario_base: Numero) -> Decimal:
        """FSR = Ps*(Tp/Tl) + Tp/Tl, redondeado a los decimales del
        proyecto (RNF-03 video 21)."""
        tp_tl = self.factor_prestaciones()
        ps = self.fraccion_cuotas(salario_base)
        return self.precision.factor(ps * tp_tl + tp_tl)

    def salario_real(self, salario_base: Numero) -> Decimal:
        return self.precision.moneda(D(salario_base) * self.factor(salario_base))

    # ------------------------------------------------------------------
    def reporte_factor_ps(self, salario_base: Numero) -> Dict[str, Decimal]:
        """Reporte "Factor PS": desglose de prestaciones sociales
        (RF-05 video 21)."""
        salario = D(salario_base)
        detalle: Dict[str, Decimal] = {}
        for cuota in self.cuotas:
            detalle[cuota.nombre] = redondear(
                cuota.fraccion(salario, self.salario_minimo_general) * 100,
                self.precision.fsr)
        if self.incluir_isn:
            detalle["Impuesto Sobre Nómina (ISN)"] = redondear(
                self.isn_pct, self.precision.fsr)
        detalle["Total Ps (%)"] = redondear(
            self.fraccion_cuotas(salario) * 100, self.precision.fsr)
        return detalle

    def reporte_fsr(self, salario_base: Numero) -> Dict[str, Decimal]:
        """Reporte "Factor de Salario Real" listo para impresión
        (RF-05 video 21)."""
        return {
            "Días pagados (Tp)": redondear(self.dias_pagados(), self.precision.fsr),
            "Días laborados (Tl)": redondear(self.dias_laborados(), self.precision.fsr),
            "Tp/Tl": redondear(self.factor_prestaciones(), self.precision.fsr),
            "Ps": redondear(self.fraccion_cuotas(salario_base), self.precision.fsr),
            "FSR": self.factor(salario_base),
        }
