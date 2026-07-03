"""Pie de Precios Unitarios (sobrecostos) — video 28.

Convierte el costo directo en precio de venta aplicando indirectos,
financiamiento, utilidad y cargos adicionales.

- RF-01 video 28: modos Estándar (porcentajes) y Avanzado (fórmulas).
- RF-02 video 28: base de cálculo Directa (sobre el costo directo) o
  Acumulable (sobre la suma acumulada), esta última el estándar en
  concursos de obra pública.
- RF-03 video 28: cargos típicos: Indirectos de Oficina, Indirectos de
  Campo, Financiamiento, Utilidad y Cargos Adicionales.
- RNF-01 video 28: el motor respeta estrictamente la jerarquía de
  aplicación configurada.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from .formulas import evaluar_formula
from .precision import ConfiguracionPrecision, D, Numero


class BaseCalculo(enum.Enum):
    DIRECTO = "Directo"
    ACUMULABLE = "Acumulable"


class ModoPie(enum.Enum):
    ESTANDAR = "Estándar"
    AVANZADO = "Avanzado"


@dataclass
class Sobrecosto:
    """Un renglón del pie de precios.

    En modo avanzado ``formula`` puede referir a las variables ``CD``
    (costo directo), ``ACUM`` (acumulado previo) y a los identificadores
    de cargos anteriores (RNF-02 video 28: fórmulas personalizadas).
    """

    identificador: str
    nombre: str
    porcentaje: Numero = 0
    base: BaseCalculo = BaseCalculo.ACUMULABLE
    formula: str | None = None
    incluye_isn: bool = False  # para validar duplicidad con el FSR


@dataclass
class RenglonPie:
    nombre: str
    porcentaje: Decimal
    base: Decimal
    importe: Decimal


@dataclass
class DetallePrecioVenta:
    costo_directo: Decimal
    renglones: List[RenglonPie]
    precio_venta: Decimal

    @property
    def factor_sobrecosto(self) -> Decimal:
        if self.costo_directo == 0:
            return Decimal(1)
        return self.precio_venta / self.costo_directo


class PiePrecios:
    """Cadena ordenada de sobrecostos del proyecto."""

    def __init__(self, modo: ModoPie = ModoPie.ESTANDAR,
                 precision: ConfiguracionPrecision | None = None) -> None:
        self.modo = modo
        self.precision = precision or ConfiguracionPrecision()
        self.cargos: List[Sobrecosto] = []

    @classmethod
    def estandar_mexicano(cls, indirectos_oficina: Numero = 0,
                          indirectos_campo: Numero = 0,
                          financiamiento: Numero = 0,
                          utilidad: Numero = 0,
                          cargos_adicionales: Numero = 0,
                          precision: ConfiguracionPrecision | None = None) -> "PiePrecios":
        """Plantilla acumulable típica de concursos de obra pública
        (RF-02/RF-03 video 28)."""
        pie = cls(ModoPie.ESTANDAR, precision)
        pie.agregar("IND_OF", "Indirectos de oficina central", indirectos_oficina)
        pie.agregar("IND_CAMPO", "Indirectos de campo", indirectos_campo)
        pie.agregar("FIN", "Financiamiento", financiamiento)
        pie.agregar("UTIL", "Utilidad", utilidad)
        pie.agregar("ADIC", "Cargos adicionales", cargos_adicionales)
        return pie

    def agregar(self, identificador: str, nombre: str, porcentaje: Numero = 0,
                base: BaseCalculo = BaseCalculo.ACUMULABLE,
                formula: str | None = None, incluye_isn: bool = False) -> Sobrecosto:
        if any(c.identificador == identificador for c in self.cargos):
            raise ValueError(f"Ya existe el cargo {identificador!r} en el pie.")
        cargo = Sobrecosto(identificador, nombre, porcentaje, base, formula, incluye_isn)
        self.cargos.append(cargo)
        return cargo

    def obtener(self, identificador: str) -> Sobrecosto:
        for cargo in self.cargos:
            if cargo.identificador == identificador:
                return cargo
        raise KeyError(f"No existe el cargo {identificador!r} en el pie.")

    def asignar_porcentaje(self, identificador: str, porcentaje: Numero) -> None:
        """Punto de inyección usado por indirectos, financiamiento y
        utilidad ("Transferir a presupuesto")."""
        self.obtener(identificador).porcentaje = D(porcentaje)

    # ------------------------------------------------------------------
    def aplicar(self, costo_directo: Numero) -> DetallePrecioVenta:
        """Calcula el precio de venta respetando la jerarquía de cargos."""
        cd = D(costo_directo)
        acumulado = cd
        variables: Dict[str, Numero] = {"CD": cd}
        renglones: List[RenglonPie] = []
        for cargo in self.cargos:
            base = cd if cargo.base == BaseCalculo.DIRECTO else acumulado
            if self.modo == ModoPie.AVANZADO and cargo.formula:
                variables["ACUM"] = acumulado
                importe = evaluar_formula(cargo.formula, variables)
            else:
                importe = base * D(cargo.porcentaje) / Decimal(100)
            variables[cargo.identificador] = importe
            renglones.append(RenglonPie(
                nombre=cargo.nombre,
                porcentaje=D(cargo.porcentaje),
                base=self.precision.moneda(base),
                importe=self.precision.moneda(importe),
            ))
            acumulado += importe
        return DetallePrecioVenta(
            costo_directo=self.precision.moneda(cd),
            renglones=renglones,
            precio_venta=self.precision.moneda(acumulado),
        )

    def precio_venta(self, costo_directo: Numero) -> Decimal:
        return self.aplicar(costo_directo).precio_venta
