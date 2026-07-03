"""INVAR Master Calculator.

Motor de cálculo para presupuestos de obra (precios unitarios, FSR,
costos horarios, indirectos, financiamiento, utilidad, programación y
explosión de insumos), desarrollado a partir de la especificación de
requerimientos derivada del análisis de OPUS Planet.
"""
from .calendario import CalendarioTrabajo, EstadoDia
from .costo_horario import DatosCostoHorario, Operador, FACTOR_HP_KW
from .explosion import ExplosionInsumos, LineaExplosion, ProgramaSuministros
from .financiamiento import (BaseAnticipo, CalculoFinanciamiento,
                             ErrorPrecondicion, ResultadoFinanciamiento)
from .formulas import FormulaInvalida, evaluar_formula
from .fsr import (CalendarioLaboralAnual, CuotaPatronal, HojaFSR,
                  PrestacionesLey, cuotas_imss_default)
from .generadores import LineaGenerador, NumerosGeneradores
from .indirectos import (CalculoIndirectos, CategoriaPersonal, GastoIndirecto,
                         MetodoOficinaCentral, PersonalIndirecto, Zona)
from .modelos import (Agrupador, Catalogo, Concepto, ContextoCalculo,
                      ErrorClaveDuplicada, ErrorReferenciaCircular, Insumo,
                      Matriz, Recurso, TipoRecurso, UNIDADES_PREDEFINIDAS)
from .moneda import Moneda, SistemaMonedas
from .pie_precios import (BaseCalculo, DetallePrecioVenta, ModoPie,
                          PiePrecios, Sobrecosto)
from .precision import ConfiguracionPrecision, D, redondear
from .programa import (Actividad, DatosRutaCritica, EscalaTiempo,
                       ProgramaObra, Segmento)
from .proyecto import DatosGenerales, Proyecto, ResumenPresupuesto
from .utilidad import CalculoUtilidad

__version__ = "0.1.0"

__all__ = [
    "Actividad", "Agrupador", "BaseAnticipo", "BaseCalculo",
    "CalculoFinanciamiento", "CalculoIndirectos", "CalculoUtilidad",
    "CalendarioLaboralAnual", "CalendarioTrabajo", "Catalogo",
    "CategoriaPersonal", "Concepto", "ConfiguracionPrecision",
    "ContextoCalculo", "CuotaPatronal", "D", "DatosCostoHorario",
    "DatosGenerales", "DatosRutaCritica", "DetallePrecioVenta",
    "ErrorClaveDuplicada", "ErrorPrecondicion", "ErrorReferenciaCircular",
    "EscalaTiempo", "EstadoDia", "ExplosionInsumos", "FACTOR_HP_KW",
    "FormulaInvalida", "GastoIndirecto", "HojaFSR", "Insumo",
    "LineaExplosion", "LineaGenerador", "Matriz", "MetodoOficinaCentral",
    "ModoPie", "Moneda", "NumerosGeneradores", "Operador",
    "PersonalIndirecto", "PiePrecios", "PrestacionesLey", "ProgramaObra",
    "ProgramaSuministros", "Proyecto", "Recurso", "ResultadoFinanciamiento",
    "ResumenPresupuesto", "Segmento", "SistemaMonedas", "Sobrecosto",
    "TipoRecurso", "UNIDADES_PREDEFINIDAS", "Zona", "cuotas_imss_default",
    "evaluar_formula", "redondear",
]
