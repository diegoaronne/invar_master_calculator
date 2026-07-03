"""Costo horario de maquinaria y equipo — videos 15 y 16.

Desglosa el costo por hora efectiva de trabajo en los tres cargos que
exige la normativa (RF-01 video 15):

1. **Cargos fijos**: depreciación, inversión, seguros y mantenimiento.
2. **Cargos por consumo**: combustible, lubricantes, llantas y piezas
   especiales.
3. **Cargos por operación**: salarios del personal operador.

Soporta el modo automático (fórmulas) y el manual (captura directa,
RF-01 video 16); los coeficientes técnicos son modificables
(RNF-02 video 16: "romper" los factores preestablecidos).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from .precision import ConfiguracionPrecision, D, Numero

#: Factor de conversión HP -> kW (RF-04 video 2, default 0.746).
FACTOR_HP_KW = Decimal("0.746")


@dataclass
class Operador:
    """Personal integrado al cargo por operación (RF-03 video 16)."""

    puesto: str
    salario_real_turno: Numero  # salario real (con FSR) por turno
    cantidad: Numero = 1


@dataclass
class DatosCostoHorario:
    """Parámetros del equipo. Los valores globales del proyecto (tasa de
    interés, prima de seguro) pueden variar por equipo (RNF-01 video 16).
    """

    # --- Cargos fijos (RF-01/RF-02/RF-03/RF-04/RF-05 video 15) ---------
    valor_adquisicion: Numero = 0        # equipo nuevo, con llantas
    valor_llantas: Numero = 0            # se deduce (vida útil distinta)
    valor_piezas_especiales: Numero = 0  # ídem
    porcentaje_rescate: Numero = 10      # % del valor deducido (Vr)
    vida_economica_anios: Numero = 5
    horas_por_anio: Numero = 2000        # horas efectivas trabajadas al año
    tasa_interes_anual_pct: Numero = 12  # ej. TIIE + sobrecosto bancario
    prima_seguro_anual_pct: Numero = 3
    factor_mantenimiento: Numero = "0.80"  # Ko sobre la depreciación

    # --- Cargos por consumo (video 16) ----------------------------------
    potencia_hp: Numero = 0
    factor_operacion: Numero = "0.80"      # fracción de la potencia usada
    coeficiente_combustible: Numero = "0.1514"  # lt/HP-hora (modificable)
    precio_combustible: Numero = 0
    capacidad_carter: Numero = 0
    horas_entre_cambios_aceite: Numero = 100
    consumo_adicional_aceite: Numero = 0   # lt/hora por fugas/relleno
    precio_lubricante: Numero = 0
    vida_llantas_horas: Numero = 0
    vida_piezas_horas: Numero = 0

    # --- Cargos por operación (RF-03 video 16) ---------------------------
    operadores: List[Operador] = field(default_factory=list)
    horas_efectivas_turno: Numero = 8   # jornada efectiva (descuenta muertos)

    # --- Modo manual (RF-01 video 16) ------------------------------------
    calculo_manual: bool = False
    combustible_manual: Numero | None = None
    lubricante_manual: Numero | None = None
    llantas_manual: Numero | None = None
    operacion_manual: Numero | None = None

    # ------------------------------------------------------------------
    def _valores_base(self) -> tuple[Decimal, Decimal, Decimal]:
        """(Va deducido, Vr, Ve en horas). RF-02 video 15: al valor de
        adquisición se le deducen llantas y piezas especiales."""
        va = (D(self.valor_adquisicion) - D(self.valor_llantas)
              - D(self.valor_piezas_especiales))
        vr = va * D(self.porcentaje_rescate) / Decimal(100)
        ve = D(self.vida_economica_anios) * D(self.horas_por_anio)
        if ve <= 0:
            raise ValueError("La vida económica en horas debe ser positiva.")
        return va, vr, ve

    def cargos_fijos(self) -> Dict[str, Decimal]:
        va, vr, ve = self._valores_base()
        hea = D(self.horas_por_anio)
        depreciacion = (va - vr) / ve
        inversion = ((va + vr) / (2 * hea)) * D(self.tasa_interes_anual_pct) / 100
        seguros = ((va + vr) / (2 * hea)) * D(self.prima_seguro_anual_pct) / 100
        mantenimiento = D(self.factor_mantenimiento) * depreciacion
        return {
            "Depreciación": depreciacion,
            "Inversión": inversion,
            "Seguros": seguros,
            "Mantenimiento": mantenimiento,
        }

    def cargos_consumo(self) -> Dict[str, Decimal]:
        detalle: Dict[str, Decimal] = {}
        if self.calculo_manual and self.combustible_manual is not None:
            detalle["Combustible"] = D(self.combustible_manual)
        else:
            gasto_hora = (D(self.coeficiente_combustible) * D(self.potencia_hp)
                          * D(self.factor_operacion))
            detalle["Combustible"] = gasto_hora * D(self.precio_combustible)
        if self.calculo_manual and self.lubricante_manual is not None:
            detalle["Lubricantes"] = D(self.lubricante_manual)
        else:
            horas_cambio = D(self.horas_entre_cambios_aceite)
            consumo = Decimal(0)
            if horas_cambio > 0:
                consumo = D(self.capacidad_carter) / horas_cambio
            consumo += D(self.consumo_adicional_aceite)
            detalle["Lubricantes"] = consumo * D(self.precio_lubricante)
        if self.calculo_manual and self.llantas_manual is not None:
            detalle["Llantas"] = D(self.llantas_manual)
        else:
            # RF-04 video 16: costo = valor / vida útil (factor 1/vida).
            detalle["Llantas"] = (
                D(self.valor_llantas) / D(self.vida_llantas_horas)
                if D(self.vida_llantas_horas) > 0 else Decimal(0))
        detalle["Piezas especiales"] = (
            D(self.valor_piezas_especiales) / D(self.vida_piezas_horas)
            if D(self.vida_piezas_horas) > 0 else Decimal(0))
        return detalle

    def cargos_operacion(self) -> Dict[str, Decimal]:
        if self.calculo_manual and self.operacion_manual is not None:
            return {"Operación": D(self.operacion_manual)}
        horas = D(self.horas_efectivas_turno)
        if horas <= 0:
            raise ValueError("Las horas efectivas por turno deben ser positivas.")
        total = Decimal(0)
        for op in self.operadores:
            # RF-03 video 16: participación por hora = salario / jornada
            # efectiva (factor 1/jornada_efectiva).
            total += D(op.salario_real_turno) * D(op.cantidad) / horas
        return {"Operación": total}

    # ------------------------------------------------------------------
    def desglose(self, precision: ConfiguracionPrecision | None = None) -> Dict[str, Dict[str, Decimal]]:
        """Desglose completo para auditoría (RNF-02 video 15) y para la
        explosión de insumos con costo horario desglosado (RF-03 video 22).
        """
        precision = precision or ConfiguracionPrecision()
        r = lambda v: precision.factor(v) if precision else v
        fijos = {k: r(v) for k, v in self.cargos_fijos().items()}
        consumos = {k: r(v) for k, v in self.cargos_consumo().items()}
        operacion = {k: r(v) for k, v in self.cargos_operacion().items()}
        return {
            "Cargos fijos": fijos,
            "Cargos por consumo": consumos,
            "Cargos por operación": operacion,
        }

    def costo_horario(self, precision: ConfiguracionPrecision | None = None) -> Decimal:
        precision = precision or ConfiguracionPrecision()
        total = Decimal(0)
        for grupo in (self.cargos_fijos(), self.cargos_consumo(), self.cargos_operacion()):
            total += sum(grupo.values(), Decimal(0))
        from .precision import redondear
        return redondear(total, precision.costo_horario)
