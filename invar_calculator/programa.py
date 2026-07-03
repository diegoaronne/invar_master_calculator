"""Programa de Obra (Gantt) — videos 23, 26 y 30.

- Programación de actividades sobre el calendario de trabajo: las
  duraciones se expresan en días laborables y las fechas se derivan del
  calendario (RNF-02 video 26).
- Fraccionamiento de cantidades en múltiples etapas (RF-04 video 26).
- Fechas administrativas del proyecto independientes de las fechas
  físicas del programa, con opción de sincronizar (RF-02 video 26).
- Ruta crítica por CPM (RF-04 video 23).
- Distribución temporal por escalas: día, semana, quincena, mes
  (RF-04 video 22, RF-03 video 23), en cantidades o montos
  (RF-05 video 22).
- Alertas de desfase temporal (RNF-01 video 26).
"""
from __future__ import annotations

import datetime as _dt
import enum
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from .calendario import CalendarioTrabajo
from .modelos import Concepto, ContextoCalculo
from .precision import D, Numero


class EscalaTiempo(enum.Enum):
    DIA = "Días"
    SEMANA = "Semanas"
    QUINCENA = "Quincenas"
    MES = "Meses"


def _etiqueta_periodo(fecha: _dt.date, escala: EscalaTiempo) -> str:
    if escala == EscalaTiempo.DIA:
        return fecha.isoformat()
    if escala == EscalaTiempo.SEMANA:
        anio, semana, _ = fecha.isocalendar()
        return f"{anio}-S{semana:02d}"
    if escala == EscalaTiempo.QUINCENA:
        quincena = 1 if fecha.day <= 15 else 2
        return f"{fecha.year}-{fecha.month:02d} Q{quincena}"
    return f"{fecha.year}-{fecha.month:02d}"


@dataclass
class Segmento:
    """Etapa de ejecución de una actividad (RF-04 video 26)."""

    inicio: _dt.date
    duracion_laborable: int
    porcentaje: Numero = 100

    def fechas(self, calendario: CalendarioTrabajo) -> Tuple[_dt.date, _dt.date]:
        inicio = calendario.siguiente_laborable(self.inicio)
        fin = calendario.sumar_laborables(inicio, self.duracion_laborable)
        return inicio, fin


class Actividad:
    def __init__(self, concepto: Concepto) -> None:
        self.concepto = concepto
        self.segmentos: List[Segmento] = []
        self.predecesoras: List["Actividad"] = []

    def agregar_segmento(self, inicio: _dt.date, duracion_laborable: int,
                         porcentaje: Numero = 100) -> Segmento:
        segmento = Segmento(inicio, duracion_laborable, porcentaje)
        self.segmentos.append(segmento)
        return segmento

    @property
    def duracion_laborable(self) -> int:
        return sum(s.duracion_laborable for s in self.segmentos)

    def fecha_inicio(self, calendario: CalendarioTrabajo) -> _dt.date:
        return min(s.fechas(calendario)[0] for s in self.segmentos)

    def fecha_fin(self, calendario: CalendarioTrabajo) -> _dt.date:
        return max(s.fechas(calendario)[1] for s in self.segmentos)

    def porcentaje_programado(self) -> Decimal:
        return sum((D(s.porcentaje) for s in self.segmentos), Decimal(0))


@dataclass
class DatosRutaCritica:
    inicio_temprano: int
    fin_temprano: int
    inicio_tardio: int
    fin_tardio: int

    @property
    def holgura(self) -> int:
        return self.inicio_tardio - self.inicio_temprano

    @property
    def es_critica(self) -> bool:
        return self.holgura == 0


class ProgramaObra:
    def __init__(self, calendario: CalendarioTrabajo | None = None,
                 fecha_inicio_proyecto: _dt.date | None = None,
                 fecha_fin_proyecto: _dt.date | None = None) -> None:
        self.calendario = calendario or CalendarioTrabajo()
        # Fechas administrativas (límites del proyecto), independientes
        # de las físicas del programa (RF-02 video 26).
        self.fecha_inicio_proyecto = fecha_inicio_proyecto
        self.fecha_fin_proyecto = fecha_fin_proyecto
        self.actividades: List[Actividad] = []
        self.alertas: List[str] = []

    # -- captura -----------------------------------------------------------
    def programar(self, concepto: Concepto, inicio: _dt.date,
                  duracion_laborable: int, porcentaje: Numero = 100,
                  predecesoras: Sequence[Actividad] | None = None) -> Actividad:
        actividad = Actividad(concepto)
        actividad.agregar_segmento(inicio, duracion_laborable, porcentaje)
        actividad.predecesoras = list(predecesoras or [])
        self.actividades.append(actividad)
        self._validar_desfase(actividad)
        return actividad

    def _validar_desfase(self, actividad: Actividad) -> None:
        """RNF-01 video 26: alerta si la actividad sale del rango del
        proyecto."""
        if self.fecha_inicio_proyecto is not None:
            inicio = actividad.fecha_inicio(self.calendario)
            if inicio < self.fecha_inicio_proyecto:
                self.alertas.append(
                    f"La actividad {actividad.concepto.clave!r} inicia el "
                    f"{inicio} antes del inicio del proyecto "
                    f"({self.fecha_inicio_proyecto}).")
        if self.fecha_fin_proyecto is not None:
            fin = actividad.fecha_fin(self.calendario)
            if fin > self.fecha_fin_proyecto:
                self.alertas.append(
                    f"La actividad {actividad.concepto.clave!r} termina el "
                    f"{fin} después del fin del proyecto "
                    f"({self.fecha_fin_proyecto}).")

    def validar_fraccionamiento(self) -> List[str]:
        """El total programado de cada actividad debe cubrir el 100% de
        la cantidad (RF-04 video 26)."""
        avisos = []
        for actividad in self.actividades:
            pct = actividad.porcentaje_programado()
            if pct != 100:
                avisos.append(
                    f"La actividad {actividad.concepto.clave!r} programa "
                    f"{pct}% de la cantidad (esperado 100%).")
        return avisos

    # -- fechas ------------------------------------------------------------
    def fechas_programa(self) -> Tuple[_dt.date, _dt.date]:
        """Fechas físicas derivadas de las actividades."""
        if not self.actividades:
            raise ValueError("No hay actividades programadas.")
        inicio = min(a.fecha_inicio(self.calendario) for a in self.actividades)
        fin = max(a.fecha_fin(self.calendario) for a in self.actividades)
        return inicio, fin

    def sincronizar_fechas(self) -> None:
        """RF-02 video 26: alinea las fechas administrativas con las del
        programa físico."""
        self.fecha_inicio_proyecto, self.fecha_fin_proyecto = self.fechas_programa()

    def auditoria(self, actividad: Actividad) -> Dict[str, object]:
        """Barra de auditoría (RF-01 video 26): fechas exactas, días
        calendario y días trabajables."""
        inicio = actividad.fecha_inicio(self.calendario)
        fin = actividad.fecha_fin(self.calendario)
        return {
            "inicio": inicio,
            "fin": fin,
            "dias_calendario": (fin - inicio).days + 1,
            "dias_trabajables": self.calendario.contar_laborables(inicio, fin),
        }

    # -- ruta crítica (RF-04 video 23) --------------------------------------
    def ruta_critica(self) -> Dict[Actividad, DatosRutaCritica]:
        if not self.actividades:
            return {}
        inicio_proyecto, _ = self.fechas_programa()
        es: Dict[Actividad, int] = {}
        ef: Dict[Actividad, int] = {}

        def offset(actividad: Actividad) -> int:
            """Arranque en días laborables relativo al inicio del programa."""
            inicio = actividad.fecha_inicio(self.calendario)
            if inicio <= inicio_proyecto:
                return 0
            return self.calendario.contar_laborables(
                inicio_proyecto, inicio - _dt.timedelta(days=1))

        pendientes = list(self.actividades)
        while pendientes:
            avanzo = False
            for actividad in list(pendientes):
                if any(p not in ef for p in actividad.predecesoras):
                    continue
                base = max((ef[p] for p in actividad.predecesoras), default=0)
                es[actividad] = max(base, offset(actividad))
                ef[actividad] = es[actividad] + actividad.duracion_laborable
                pendientes.remove(actividad)
                avanzo = True
            if not avanzo:
                raise ValueError("Dependencias circulares en el programa.")

        fin_proyecto = max(ef.values())
        lf: Dict[Actividad, int] = {}
        ls: Dict[Actividad, int] = {}
        sucesoras: Dict[Actividad, List[Actividad]] = {a: [] for a in self.actividades}
        for actividad in self.actividades:
            for p in actividad.predecesoras:
                sucesoras[p].append(actividad)
        for actividad in sorted(self.actividades, key=lambda a: -ef[a]):
            if sucesoras[actividad]:
                lf[actividad] = min(ls[s] for s in sucesoras[actividad])
            else:
                lf[actividad] = fin_proyecto
            ls[actividad] = lf[actividad] - actividad.duracion_laborable

        return {
            a: DatosRutaCritica(es[a], ef[a], ls[a], lf[a])
            for a in self.actividades
        }

    def actividades_criticas(self) -> List[Actividad]:
        return [a for a, datos in self.ruta_critica().items() if datos.es_critica]

    # -- distribución temporal ------------------------------------------------
    def distribuir_actividad(self, actividad: Actividad, escala: EscalaTiempo,
                             total: Numero) -> Dict[str, Decimal]:
        """Reparte ``total`` proporcionalmente a las horas laborables de
        cada día de los segmentos, agrupado por periodo."""
        distribucion: Dict[str, Decimal] = {}
        total = D(total)
        for segmento in actividad.segmentos:
            monto_segmento = total * D(segmento.porcentaje) / 100
            inicio, fin = segmento.fechas(self.calendario)
            dias = self.calendario.dias_laborables(inicio, fin)
            horas_totales = sum((self.calendario.horas(d) for d in dias), Decimal(0))
            if horas_totales == 0:
                continue
            for dia in dias:
                proporcion = self.calendario.horas(dia) / horas_totales
                etiqueta = _etiqueta_periodo(dia, escala)
                distribucion[etiqueta] = (
                    distribucion.get(etiqueta, Decimal(0))
                    + monto_segmento * proporcion)
        return dict(sorted(distribucion.items()))

    def programa_cantidades(self, escala: EscalaTiempo) -> Dict[str, Dict[str, Decimal]]:
        """Cantidades por concepto y periodo (RF-03 video 23, vista A)."""
        resultado: Dict[str, Dict[str, Decimal]] = {}
        for actividad in self.actividades:
            clave = actividad.concepto.clave
            parcial = self.distribuir_actividad(
                actividad, escala, actividad.concepto.cantidad_efectiva)
            destino = resultado.setdefault(clave, {})
            for etiqueta, cantidad in parcial.items():
                destino[etiqueta] = destino.get(etiqueta, Decimal(0)) + cantidad
        return resultado

    def programa_montos(self, escala: EscalaTiempo, ctx: ContextoCalculo,
                        con_sobrecostos: bool = True) -> Dict[str, Decimal]:
        """Flujo económico por periodo (RF-03 video 23, vista B). Es el
        insumo del cálculo de financiamiento."""
        resultado: Dict[str, Decimal] = {}
        for actividad in self.actividades:
            pu = actividad.concepto.costo_directo_unitario(ctx)
            if con_sobrecostos:
                pu = ctx.precio_venta(pu)
            monto = pu * actividad.concepto.cantidad_efectiva
            parcial = self.distribuir_actividad(actividad, escala, monto)
            for etiqueta, importe in parcial.items():
                resultado[etiqueta] = resultado.get(etiqueta, Decimal(0)) + importe
        return dict(sorted(resultado.items()))
