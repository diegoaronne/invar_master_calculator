"""Proyecto: raíz que integra catálogo, WBS, FSR, pie de precios,
calendario y programa — videos 1, 2 y 28.

- RF-01 video 1: nombre de hasta 128 caracteres.
- RF-02 video 1: parámetros generales (Datos y Configuración).
- RF-04 video 1: catálogos de personal (responsables) y registros.
- RF-05 video 1: decimales, IVA y monedas.
- RF-04 video 28: "Recalcular obra" tras cambiar el pie de precios.
- RNF-02 video 21: validación de duplicidad de ISN entre FSR y cargos
  adicionales.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Iterator, List, Optional

from .calendario import CalendarioTrabajo
from .fsr import HojaFSR
from .modelos import Agrupador, Catalogo, Concepto, Matriz
from .moneda import SistemaMonedas
from .pie_precios import PiePrecios
from .precision import ConfiguracionPrecision, D, Numero
from .programa import ProgramaObra

NOMBRE_MAXIMO = 128


@dataclass
class DatosGenerales:
    """Datos de identificación de la obra (RF-02/RF-04 video 1)."""

    cliente: str = ""
    autor: str = ""
    descripcion_obra: str = ""
    ubicacion: str = ""
    fecha_inicio: Optional[_dt.date] = None
    fecha_fin: Optional[_dt.date] = None
    responsables: List[str] = field(default_factory=list)
    registros: List[str] = field(default_factory=list)


@dataclass
class ResumenPresupuesto:
    costo_directo: Decimal
    precio_venta: Decimal
    iva: Decimal
    total_con_iva: Decimal


class Proyecto:
    def __init__(self, nombre: str,
                 datos: DatosGenerales | None = None,
                 precision: ConfiguracionPrecision | None = None,
                 iva_pct: Numero = 16) -> None:
        if not nombre or len(nombre) > NOMBRE_MAXIMO:
            raise ValueError(
                f"El nombre del proyecto debe tener entre 1 y {NOMBRE_MAXIMO} "
                "caracteres (RF-01 video 1).")
        self.nombre = nombre
        self.datos = datos or DatosGenerales()
        self.precision = precision or ConfiguracionPrecision()
        self.iva_pct = D(iva_pct)
        self.monedas = SistemaMonedas()
        self.catalogo = Catalogo()
        self.raiz = Agrupador(clave="", descripcion=nombre)
        self.hoja_fsr = HojaFSR(precision=self.precision)
        self.pie = PiePrecios.estandar_mexicano(precision=self.precision)
        self.calendario = CalendarioTrabajo()
        self.programa = ProgramaObra(
            self.calendario,
            fecha_inicio_proyecto=self.datos.fecha_inicio,
            fecha_fin_proyecto=self.datos.fecha_fin)

    # -- interfaz ContextoCalculo -----------------------------------------
    def fsr_factor(self, salario_base: Decimal) -> Decimal:
        return self.hoja_fsr.factor(salario_base)

    def precio_venta(self, costo_directo: Decimal) -> Decimal:
        return self.pie.precio_venta(costo_directo)

    # -- construcción -------------------------------------------------------
    def crear_matriz(self, clave: str, descripcion: str = "",
                     unidad: str = "pza") -> Matriz:
        """Crea (o reutiliza) una matriz registrada en el catálogo, de
        modo que pueda vincularse a varios conceptos (RF-06 video 4)."""
        if clave in self.catalogo:
            existente = self.catalogo.obtener(clave)
            if isinstance(existente, Matriz):
                return existente
            raise ValueError(f"La clave {clave!r} ya existe y no es una matriz.")
        matriz = Matriz(clave, descripcion, unidad)
        self.catalogo.registrar(matriz)
        return matriz

    def iter_conceptos(self) -> Iterator[Concepto]:
        return self.raiz.iter_conceptos()

    # -- cálculo --------------------------------------------------------------
    def costo_directo_total(self) -> Decimal:
        total = Decimal(0)
        for concepto in self.iter_conceptos():
            pu = self.precision.moneda(concepto.costo_directo_unitario(self))
            total += pu * concepto.cantidad_efectiva
        return self.precision.moneda(total)

    def recalcular(self) -> ResumenPresupuesto:
        """RF-04 video 28: "Recalcular la obra" — actualiza todos los
        conceptos con los sobrecostos vigentes del pie de precios."""
        costo_directo = Decimal(0)
        venta = Decimal(0)
        for concepto in self.iter_conceptos():
            pu_directo = self.precision.moneda(concepto.costo_directo_unitario(self))
            pu_venta = self.precision.moneda(self.pie.precio_venta(pu_directo))
            cantidad = concepto.cantidad_efectiva
            costo_directo += pu_directo * cantidad
            venta += pu_venta * cantidad
        iva = self.precision.moneda(venta * self.iva_pct / 100)
        return ResumenPresupuesto(
            costo_directo=self.precision.moneda(costo_directo),
            precio_venta=self.precision.moneda(venta),
            iva=iva,
            total_con_iva=self.precision.moneda(venta + iva),
        )

    # -- validaciones -----------------------------------------------------------
    def validar(self) -> List[str]:
        """Mecanismos de control de calidad previos a la entrega."""
        avisos: List[str] = []
        # RNF-02 video 21: el ISN no debe contabilizarse doble (FSR y
        # cargos adicionales).
        if self.hoja_fsr.incluir_isn:
            for cargo in self.pie.cargos:
                if cargo.incluye_isn and D(cargo.porcentaje) != 0:
                    avisos.append(
                        f"Posible duplicidad de ISN: el FSR ya lo incluye y el "
                        f"cargo {cargo.nombre!r} también lo considera.")
        avisos.extend(self.programa.alertas)
        avisos.extend(self.programa.validar_fraccionamiento())
        return avisos
