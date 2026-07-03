"""Costos indirectos — video 29 (Art. 180 RLOPSRM).

Diferencia gastos de Oficina Central y Oficina de Campo (RF-01),
soporta tres métodos de cálculo para oficina central (RF-02):

- ``PORCENTAJE``: porcentaje directo del gasto operativo total.
- ``ANUALIZADO``: gasto anual de oficina / ingresos anuales de obra.
- ``DETALLADO``: plantillas de personal y gastos prorrateadas a la obra.

Las plantillas desglosan personal directivo/técnico/administrativo con
salario base + FSR (o factor manual, RNF-02) y gastos generales (RF-03).
"Aplicar" calcula los porcentajes resultantes y "Transferir" los inyecta
al pie de precios (RF-04); el impacto puede monitorearse antes (RF-05).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Dict, List, Optional

from .pie_precios import PiePrecios
from .precision import ConfiguracionPrecision, D, Numero, redondear


class Zona(enum.Enum):
    CENTRAL = "Oficina central"
    CAMPO = "Oficina de campo"


class CategoriaPersonal(enum.Enum):
    DIRECTIVO = "Personal directivo"
    TECNICO = "Personal técnico"
    ADMINISTRATIVO = "Personal administrativo"


class MetodoOficinaCentral(enum.Enum):
    PORCENTAJE = "Porcentaje del gasto total"
    ANUALIZADO = "Anualizado"
    DETALLADO = "Plantillas detalladas"


@dataclass
class PersonalIndirecto:
    puesto: str
    salario_base_mensual: Numero
    meses: Numero
    zona: Zona = Zona.CAMPO
    categoria: CategoriaPersonal = CategoriaPersonal.TECNICO
    usa_fsr: bool = True          # RNF-02 video 29
    fsr_manual: Numero | None = None
    cantidad: Numero = 1

    def importe(self, fsr_factor: Callable[[Decimal], Decimal]) -> Decimal:
        salario = D(self.salario_base_mensual)
        if self.fsr_manual is not None:
            factor = D(self.fsr_manual)
        elif self.usa_fsr:
            factor = fsr_factor(salario)
        else:
            factor = Decimal(1)
        return salario * factor * D(self.meses) * D(self.cantidad)


@dataclass
class GastoIndirecto:
    concepto: str
    importe_mensual: Numero
    meses: Numero
    zona: Zona = Zona.CAMPO

    def importe(self) -> Decimal:
        return D(self.importe_mensual) * D(self.meses)


class CalculoIndirectos:
    def __init__(self,
                 metodo_oficina_central: MetodoOficinaCentral = MetodoOficinaCentral.DETALLADO,
                 porcentaje_gasto_total: Numero = 0,
                 gasto_anual_oficina: Numero = 0,
                 ingresos_anuales_obras: Numero = 0,
                 duracion_obra_meses: Numero = 0,
                 precision: ConfiguracionPrecision | None = None) -> None:
        self.metodo_oficina_central = metodo_oficina_central
        self.porcentaje_gasto_total = D(porcentaje_gasto_total)
        self.gasto_anual_oficina = D(gasto_anual_oficina)
        self.ingresos_anuales_obras = D(ingresos_anuales_obras)
        self.duracion_obra_meses = D(duracion_obra_meses)
        self.precision = precision or ConfiguracionPrecision()
        self.personal: List[PersonalIndirecto] = []
        self.gastos: List[GastoIndirecto] = []

    # -- plantillas ------------------------------------------------------
    def agregar_personal(self, persona: PersonalIndirecto) -> PersonalIndirecto:
        self.personal.append(persona)
        return persona

    def agregar_gasto(self, gasto: GastoIndirecto) -> GastoIndirecto:
        self.gastos.append(gasto)
        return gasto

    # -- totales ----------------------------------------------------------
    def total_zona(self, zona: Zona,
                   fsr_factor: Callable[[Decimal], Decimal]) -> Decimal:
        total = Decimal(0)
        for p in self.personal:
            if p.zona == zona:
                total += p.importe(fsr_factor)
        for g in self.gastos:
            if g.zona == zona:
                total += g.importe()
        return total

    def desglose_personal(self, fsr_factor: Callable[[Decimal], Decimal]) -> List[Dict]:
        """Vista "Datos completos" para auditoría (RNF-01 video 29)."""
        filas = []
        for p in self.personal:
            filas.append({
                "puesto": p.puesto,
                "categoria": p.categoria.value,
                "zona": p.zona.value,
                "salario_base_mensual": self.precision.moneda(p.salario_base_mensual),
                "meses": D(p.meses),
                "importe": self.precision.moneda(p.importe(fsr_factor)),
            })
        return filas

    # -- porcentajes -------------------------------------------------------
    def porcentaje_oficina_central(self, costo_directo: Numero,
                                   fsr_factor: Callable[[Decimal], Decimal]) -> Decimal:
        cd = D(costo_directo)
        if self.metodo_oficina_central == MetodoOficinaCentral.PORCENTAJE:
            pct = self.porcentaje_gasto_total
        elif self.metodo_oficina_central == MetodoOficinaCentral.ANUALIZADO:
            # RF-02 video 29: gasto anual de oficina central entre el
            # ingreso por obras del ejercicio (anterior o estimado).
            if self.ingresos_anuales_obras == 0:
                raise ValueError("El método anualizado requiere ingresos anuales.")
            pct = self.gasto_anual_oficina / self.ingresos_anuales_obras * 100
        else:
            if cd == 0:
                raise ValueError("Se requiere el costo directo de la obra.")
            pct = self.total_zona(Zona.CENTRAL, fsr_factor) / cd * 100
        return redondear(pct, self.precision.porcentajes)

    def porcentaje_oficina_campo(self, costo_directo: Numero,
                                 fsr_factor: Callable[[Decimal], Decimal]) -> Decimal:
        cd = D(costo_directo)
        if cd == 0:
            raise ValueError("Se requiere el costo directo de la obra.")
        pct = self.total_zona(Zona.CAMPO, fsr_factor) / cd * 100
        return redondear(pct, self.precision.porcentajes)

    def aplicar(self, costo_directo: Numero,
                fsr_factor: Callable[[Decimal], Decimal]) -> Dict[str, Decimal]:
        """RF-04/RF-05 video 29: "Aplicar Indirectos" — porcentajes
        resultantes para monitoreo previo a la transferencia."""
        return {
            "oficina_central": self.porcentaje_oficina_central(costo_directo, fsr_factor),
            "oficina_campo": self.porcentaje_oficina_campo(costo_directo, fsr_factor),
        }

    def transferir_a(self, pie: PiePrecios, costo_directo: Numero,
                     fsr_factor: Callable[[Decimal], Decimal],
                     id_oficina: str = "IND_OF",
                     id_campo: str = "IND_CAMPO") -> Dict[str, Decimal]:
        """RF-04 video 29: "Transferir" migra los valores calculados al
        pie de precios unitarios del proyecto."""
        resultado = self.aplicar(costo_directo, fsr_factor)
        pie.asignar_porcentaje(id_oficina, resultado["oficina_central"])
        pie.asignar_porcentaje(id_campo, resultado["oficina_campo"])
        return resultado
