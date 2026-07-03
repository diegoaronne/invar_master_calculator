"""Calendario de Trabajo — video 24.

Define la capacidad de trabajo de cada día mediante cuatro estados
(RF-01): Trabajable (jornada completa), No trabajable, Medio trabajable
y Personalizado (horas específicas). La configuración actúa como
restricción del motor de programación (RNF-01): las fechas del Gantt se
calculan solo sobre días con horas disponibles.
"""
from __future__ import annotations

import datetime as _dt
import enum
from decimal import Decimal
from typing import Dict, Iterator, List, Optional

from .precision import D, Numero


class EstadoDia(enum.Enum):
    TRABAJABLE = "Trabajable"
    NO_TRABAJABLE = "No trabajable"
    MEDIO_TRABAJABLE = "Medio trabajable"
    PERSONALIZADO = "Personalizado"


class CalendarioTrabajo:
    """Calendario configurable por reglas semanales y excepciones puntuales.

    - RF-02 video 24: interacción por fecha (marcar festivos, medios días).
    - RF-03 video 24: jornadas específicas para fechas puntuales
      (ej. 5 horas el 24 y 31 de diciembre).
    - RNF-03 video 24: adaptable a lo estipulado en bases de concurso.
    """

    def __init__(self, horas_jornada: Numero = 8) -> None:
        self.horas_jornada = D(horas_jornada)
        # Regla semanal por defecto: lunes a viernes completos, sábado
        # medio día, domingo no trabajable (escenario típico de obra).
        self._reglas_semana: Dict[int, EstadoDia] = {
            0: EstadoDia.TRABAJABLE, 1: EstadoDia.TRABAJABLE,
            2: EstadoDia.TRABAJABLE, 3: EstadoDia.TRABAJABLE,
            4: EstadoDia.TRABAJABLE, 5: EstadoDia.MEDIO_TRABAJABLE,
            6: EstadoDia.NO_TRABAJABLE,
        }
        self._excepciones: Dict[_dt.date, Decimal] = {}

    # -- configuración ---------------------------------------------------
    def configurar_dia_semana(self, dia_semana: int, estado: EstadoDia) -> None:
        """0 = lunes ... 6 = domingo."""
        if estado == EstadoDia.PERSONALIZADO:
            raise ValueError("Para jornadas personalizadas use marcar().")
        self._reglas_semana[dia_semana] = estado

    def marcar(self, fecha: _dt.date, estado: EstadoDia,
               horas: Numero | None = None) -> None:
        """Marca un día puntual (RF-02/RF-03 video 24)."""
        self._excepciones[fecha] = self._horas_estado(estado, horas)

    def marcar_rango(self, desde: _dt.date, hasta: _dt.date,
                     estado: EstadoDia, horas: Numero | None = None) -> None:
        fecha = desde
        while fecha <= hasta:
            self.marcar(fecha, estado, horas)
            fecha += _dt.timedelta(days=1)

    def _horas_estado(self, estado: EstadoDia, horas: Numero | None) -> Decimal:
        if estado == EstadoDia.TRABAJABLE:
            return self.horas_jornada
        if estado == EstadoDia.NO_TRABAJABLE:
            return Decimal(0)
        if estado == EstadoDia.MEDIO_TRABAJABLE:
            return self.horas_jornada / 2
        if horas is None:
            raise ValueError("El estado Personalizado requiere las horas.")
        return D(horas)

    # -- consultas ---------------------------------------------------------
    def horas(self, fecha: _dt.date) -> Decimal:
        if fecha in self._excepciones:
            return self._excepciones[fecha]
        estado = self._reglas_semana.get(fecha.weekday(), EstadoDia.TRABAJABLE)
        return self._horas_estado(estado, None)

    def es_laborable(self, fecha: _dt.date) -> bool:
        return self.horas(fecha) > 0

    def siguiente_laborable(self, fecha: _dt.date) -> _dt.date:
        while not self.es_laborable(fecha):
            fecha += _dt.timedelta(days=1)
        return fecha

    def dias_laborables(self, desde: _dt.date, hasta: _dt.date) -> List[_dt.date]:
        """Días con capacidad de trabajo en el rango [desde, hasta]."""
        dias = []
        fecha = desde
        while fecha <= hasta:
            if self.es_laborable(fecha):
                dias.append(fecha)
            fecha += _dt.timedelta(days=1)
        return dias

    def contar_laborables(self, desde: _dt.date, hasta: _dt.date) -> int:
        """Auditoría de fechas: días trabajables del rango (RF-01 v26)."""
        return len(self.dias_laborables(desde, hasta))

    def sumar_laborables(self, inicio: _dt.date, dias: int) -> _dt.date:
        """Fecha resultante de avanzar ``dias`` laborables desde
        ``inicio`` (inclusive). Motor base del Gantt (RNF-01 video 24)."""
        if dias <= 0:
            raise ValueError("La duración debe ser de al menos 1 día laborable.")
        fecha = self.siguiente_laborable(inicio)
        restantes = dias - 1
        while restantes > 0:
            fecha = self.siguiente_laborable(fecha + _dt.timedelta(days=1))
            restantes -= 1
        return fecha
