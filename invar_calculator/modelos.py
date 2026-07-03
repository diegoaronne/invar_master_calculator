"""Modelos centrales: recursos, insumos, matrices, catálogo, conceptos y WBS.

Implementa, entre otros:
- Los 8 tipos de recursos con alias configurables (RF-05 video 2).
- Matrices de precio unitario con insumos de cualquier naturaleza,
  anidación ilimitada y prevención de referencias circulares
  (RF-05/RF-06 video 4, RNF-03 video 12, RNF-03 video 18).
- Recursos compuestos (cuadrillas, auxiliares) con desglose recursivo
  (RF-01 video 14, RF-02 video 18).
- Herramienta como porcentaje de mano de obra "%MO" (RF-01/RF-02 video 17).
- Catálogo maestro con vinculación por clave, homologación de duplicados,
  trazabilidad "dónde participa" y conversión de tipo (videos 13 y 20).
- Estructura WBS de agrupadores con niveles ilimitados y borrado en
  cascada (videos 5 y 8).
"""
from __future__ import annotations

import datetime as _dt
import enum
import fnmatch
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Union

from .formulas import evaluar_formula
from .precision import ConfiguracionPrecision, D, Numero


class TipoRecurso(enum.Enum):
    """Los 8 tipos de recurso predeterminados (RF-02 video 12)."""

    MATERIAL = "Material"
    MANO_OBRA = "Mano de obra"
    HERRAMIENTA = "Herramienta"
    EQUIPO = "Equipo"
    AUXILIAR = "Auxiliar"
    FLETE = "Flete"
    SUBCONTRATO = "Subcontrato"
    MATRIZ = "Matriz"


#: Unidades de medida validadas (RNF-03 video 6: evitar "M2" vs "m2").
UNIDADES_PREDEFINIDAS = {
    "m", "m2", "m3", "ml", "km", "kg", "ton", "lt", "pza", "lote", "jor",
    "hr", "día", "mes", "sal", "viaje", "ha", "ml3", "%mo", "juego", "rollo",
}


class ErrorClaveDuplicada(ValueError):
    pass


class ErrorReferenciaCircular(ValueError):
    pass


@dataclass
class Insumo:
    """Participación de un recurso dentro de una matriz o compuesto.

    ``cantidad`` acepta un número o una fórmula ("2/20") conforme a
    RF-04 / RNF-02 del video 14.
    """

    recurso: "Recurso"
    cantidad: Numero = 1

    @property
    def cantidad_decimal(self) -> Decimal:
        if isinstance(self.cantidad, str):
            return evaluar_formula(self.cantidad)
        return D(self.cantidad)


@dataclass
class Recurso:
    clave: str
    descripcion: str = ""
    unidad: str = "pza"
    tipo: TipoRecurso = TipoRecurso.MATERIAL
    costo: Numero = 0
    moneda: str | None = None
    familia: str = ""
    subfamilia: str = ""
    fecha_vigencia: Optional[_dt.date] = None
    indivisible: bool = False  # RF-04 video 13: fuerza enteros en explosión
    formula_costo: str | None = None  # RF-03 video 13
    variables_costo: Dict[str, Numero] = field(default_factory=dict)
    componentes: List[Insumo] = field(default_factory=list)

    # Campos específicos de mano de obra (video 14)
    salario_base: Numero | None = None
    usa_fsr: bool = True
    fsr_manual: Numero | None = None

    # Datos de costo horario para equipo (videos 15-16); se asigna un
    # objeto invar_calculator.costo_horario.DatosCostoHorario
    datos_costo_horario: object | None = None

    def __post_init__(self) -> None:
        if self.tipo == TipoRecurso.HERRAMIENTA and self.unidad == "pza":
            # RF-01 video 17: la herramienta nace como %MO por defecto.
            self.unidad = "%mo"

    # ------------------------------------------------------------------
    @property
    def es_compuesto(self) -> bool:
        return bool(self.componentes)

    @property
    def es_porcentaje_mo(self) -> bool:
        return self.unidad.lower() == "%mo"

    def agregar_componente(self, recurso: "Recurso", cantidad: Numero = 1) -> Insumo:
        _validar_no_circular(self, recurso)
        insumo = Insumo(recurso, cantidad)
        self.componentes.append(insumo)
        return insumo

    def quitar_componente(self, clave: str) -> None:
        self.componentes = [i for i in self.componentes if i.recurso.clave != clave]

    # ------------------------------------------------------------------
    def costo_unitario(self, ctx: "ContextoCalculo") -> Decimal:
        """Costo unitario del recurso en moneda base.

        Orden de resolución:
        1. Equipo con datos de costo horario -> motor de costo horario.
        2. Mano de obra con salario base -> salario real vía FSR
           (RF-02 video 14) o factor manual (RNF-01 video 14).
        3. Compuesto -> suma de componentes (RNF-03 video 14, RNF-01 v18).
        4. Fórmula de costo (RF-03 video 13).
        5. Costo capturado, convertido de su moneda a la base.
        """
        if self.datos_costo_horario is not None:
            return self.datos_costo_horario.costo_horario(ctx.precision)  # type: ignore[attr-defined]
        if self.tipo == TipoRecurso.MANO_OBRA and self.salario_base is not None:
            salario = D(self.salario_base)
            if self.fsr_manual is not None:
                factor = D(self.fsr_manual)
            elif self.usa_fsr:
                factor = ctx.fsr_factor(salario)
            else:
                factor = Decimal(1)
            return ctx.precision.moneda(salario * factor)
        if self.es_compuesto:
            total = Decimal(0)
            costo_mo = Decimal(0)
            for insumo in self.componentes:
                if insumo.recurso.es_porcentaje_mo:
                    continue
                importe = insumo.cantidad_decimal * insumo.recurso.costo_unitario(ctx)
                total += importe
                if insumo.recurso.tipo == TipoRecurso.MANO_OBRA:
                    costo_mo += importe
            for insumo in self.componentes:
                if insumo.recurso.es_porcentaje_mo:
                    total += insumo.cantidad_decimal * costo_mo
            return ctx.precision.moneda(total)
        if self.formula_costo:
            return ctx.precision.moneda(
                evaluar_formula(self.formula_costo, self.variables_costo)
            )
        return ctx.precision.moneda(ctx.monedas.a_base(self.costo, self.moneda))

    # ------------------------------------------------------------------
    def iter_recursivo(self) -> Iterator["Recurso"]:
        """Recorre el árbol de composición (incluyéndose a sí mismo)."""
        yield self
        for insumo in self.componentes:
            yield from insumo.recurso.iter_recursivo()


def _validar_no_circular(padre: Recurso, nuevo: Recurso) -> None:
    """RNF-03 video 12 / video 18: una matriz o auxiliar no puede
    contenerse a sí misma directa ni indirectamente."""
    for r in nuevo.iter_recursivo():
        if r is padre:
            raise ErrorReferenciaCircular(
                f"El recurso {nuevo.clave!r} contiene (o es) {padre.clave!r}; "
                "se generaría una referencia circular."
            )


class Matriz(Recurso):
    """Matriz de precio unitario: análisis de costo de un concepto.

    Concepto y matriz son objetos independientes (RNF-03 video 4,
    RNF-03 video 25): una misma matriz puede vincularse a varios conceptos
    y su desglose puede copiarse sin copiar el concepto.
    """

    def __init__(self, clave: str, descripcion: str = "", unidad: str = "pza") -> None:
        super().__init__(clave=clave, descripcion=descripcion, unidad=unidad,
                         tipo=TipoRecurso.MATRIZ)

    @property
    def insumos(self) -> List[Insumo]:
        return self.componentes

    def agregar_insumo(self, recurso: Recurso, cantidad: Numero = 1) -> Insumo:
        return self.agregar_componente(recurso, cantidad)

    def insumos_por_tipo(self, tipo: TipoRecurso) -> List[Insumo]:
        """RF-02 video 12: filtro instantáneo por naturaleza del insumo."""
        return [i for i in self.componentes if i.recurso.tipo == tipo]

    def copiar_desglose_desde(self, fuente: "Matriz",
                              reemplazar_existentes: bool = True) -> None:
        """RF-03/RF-04 video 25: copia solo el desglose (insumos) de otra
        matriz, con resolución de conflictos por clave."""
        existentes = {i.recurso.clave: i for i in self.componentes}
        for insumo in fuente.componentes:
            if insumo.recurso.clave in existentes:
                if reemplazar_existentes:
                    self.quitar_componente(insumo.recurso.clave)
                    self.agregar_componente(insumo.recurso, insumo.cantidad)
            else:
                self.agregar_componente(insumo.recurso, insumo.cantidad)

    def resumen_por_tipo(self, ctx: "ContextoCalculo") -> Dict[str, Decimal]:
        """RF-04 video 12: desglose del costo directo por naturaleza."""
        total = self.costo_unitario(ctx)
        resumen: Dict[str, Decimal] = {}
        costo_mo = sum(
            (i.cantidad_decimal * i.recurso.costo_unitario(ctx)
             for i in self.componentes
             if i.recurso.tipo == TipoRecurso.MANO_OBRA), Decimal(0))
        for insumo in self.componentes:
            nombre = insumo.recurso.tipo.value
            if insumo.recurso.es_porcentaje_mo:
                importe = insumo.cantidad_decimal * costo_mo
            else:
                importe = insumo.cantidad_decimal * insumo.recurso.costo_unitario(ctx)
            resumen[nombre] = resumen.get(nombre, Decimal(0)) + importe
        resumen["Total"] = total
        return resumen


# ----------------------------------------------------------------------
class Catalogo:
    """Catálogo maestro de recursos del proyecto (video 20)."""

    def __init__(self) -> None:
        self._recursos: Dict[str, Recurso] = {}
        #: Alias de naturalezas, modificable (RF-05 video 2).
        self.alias_tipos: Dict[TipoRecurso, str] = {t: t.value for t in TipoRecurso}

    def __contains__(self, clave: str) -> bool:
        return clave in self._recursos

    def __len__(self) -> int:
        return len(self._recursos)

    def obtener(self, clave: str) -> Recurso:
        return self._recursos[clave]

    def registrar(self, recurso: Recurso) -> Recurso:
        """Registra un recurso. Si la clave ya existe, regresa el existente
        para vincularlo en lugar de duplicar (RNF-02 video 13)."""
        existente = self._recursos.get(recurso.clave)
        if existente is not None:
            return existente
        self._recursos[recurso.clave] = recurso
        return recurso

    def crear(self, clave: str, **kwargs) -> Recurso:
        if clave in self._recursos:
            return self._recursos[clave]
        recurso = Recurso(clave=clave, **kwargs)
        self._recursos[clave] = recurso
        return recurso

    def por_tipo(self, tipo: TipoRecurso) -> List[Recurso]:
        """RF-01 video 20: vistas segmentadas por tipo de recurso."""
        return [r for r in self._recursos.values() if r.tipo == tipo]

    def buscar(self, patron: str) -> List[Recurso]:
        """Búsqueda con comodines * en clave o descripción
        (RF-04 video 7, RF-02 video 9)."""
        patron = patron.lower()
        if "*" not in patron:
            patron = f"*{patron}*"
        return [
            r for r in self._recursos.values()
            if fnmatch.fnmatch(r.clave.lower(), patron)
            or fnmatch.fnmatch(r.descripcion.lower(), patron)
        ]

    def donde_participa(self, clave: str, recursivo: bool = True) -> List[Recurso]:
        """RF-04 video 20 / RF-03 video 18: trazabilidad de uso.

        Con ``recursivo=True`` regresa todo recurso en cuya composición
        (a cualquier profundidad) participa la clave; con ``False`` solo
        los que lo contienen como insumo directo.
        """
        objetivo = self._recursos[clave]
        usuarios: List[Recurso] = []
        for r in self._recursos.values():
            if r is objetivo:
                continue
            if recursivo:
                usa = any(x is objetivo for x in r.iter_recursivo() if x is not r)
            else:
                usa = any(h is objetivo for h in _hijos_directos(r))
            if usa:
                usuarios.append(r)
        return usuarios

    def homologar(self, claves_duplicadas: Sequence[str], clave_maestra: str) -> None:
        """RF-03 video 20: fusiona duplicados apuntando todo al maestro."""
        maestro = self._recursos[clave_maestra]
        duplicados = {c: self._recursos[c] for c in claves_duplicadas if c != clave_maestra}
        for r in self._recursos.values():
            for insumo in r.componentes:
                if insumo.recurso.clave in duplicados:
                    insumo.recurso = maestro
        for clave in duplicados:
            del self._recursos[clave]

    def cambiar_tipo(self, clave: str, nuevo_tipo: TipoRecurso) -> Recurso:
        """RF-05 video 20: conversión de naturaleza conservando referencias."""
        recurso = self._recursos[clave]
        recurso.tipo = nuevo_tipo
        return recurso

    def reemplazar_referencias(self, matriz: Recurso,
                               conservar_existentes: bool = False) -> None:
        """RF-03 video 7 / RF-03 video 8: al importar una matriz externa,
        vincula sus insumos al catálogo. Si la clave ya existe se decide
        entre conservar el recurso local o reemplazarlo por el importado."""
        for insumo in matriz.componentes:
            clave = insumo.recurso.clave
            if clave in self._recursos:
                if conservar_existentes:
                    insumo.recurso = self._recursos[clave]
                else:
                    self._recursos[clave] = insumo.recurso
            else:
                self._recursos[clave] = insumo.recurso
            if insumo.recurso.es_compuesto:
                self.reemplazar_referencias(insumo.recurso, conservar_existentes)


def _hijos_directos(recurso: Recurso) -> Iterator[Recurso]:
    for insumo in recurso.componentes:
        yield insumo.recurso


# ----------------------------------------------------------------------
@dataclass
class Concepto:
    """Actividad o proceso constructivo del presupuesto (video 6)."""

    clave: str
    descripcion: str = ""
    unidad: str = "pza"
    cantidad: Numero = 0
    matriz: Optional[Matriz] = None
    generador: Optional[object] = None  # invar_calculator.generadores.NumerosGeneradores

    def __post_init__(self) -> None:
        if self.unidad and self.unidad.lower() not in UNIDADES_PREDEFINIDAS:
            # RNF-03 video 6: unidad apoyada en lista de validación.
            raise ValueError(
                f"Unidad {self.unidad!r} no reconocida; registrar en "
                "UNIDADES_PREDEFINIDAS o usar una unidad estándar."
            )

    @property
    def cantidad_efectiva(self) -> Decimal:
        """Si hay números generadores activos, la cantidad proviene de
        ellos (RNF-02 video 10); si no, de la captura directa."""
        if self.generador is not None:
            return self.generador.cantidad_total()  # type: ignore[attr-defined]
        return D(self.cantidad)

    def costo_directo_unitario(self, ctx: "ContextoCalculo") -> Decimal:
        if self.matriz is None:
            return Decimal(0)
        return self.matriz.costo_unitario(ctx)


class Agrupador:
    """Nodo de la estructura WBS (capítulo/partida) — video 5."""

    def __init__(self, clave: str = "", descripcion: str = "") -> None:
        self.clave = clave
        self.descripcion = descripcion
        self.hijos: List[Union["Agrupador", Concepto]] = []
        self.padre: Optional["Agrupador"] = None

    # -- construcción ---------------------------------------------------
    def agregar_agrupador(self, clave: str = "", descripcion: str = "") -> "Agrupador":
        hijo = Agrupador(clave, descripcion)
        hijo.padre = self
        self.hijos.append(hijo)
        return hijo

    def agregar_concepto(self, concepto: Concepto) -> Concepto:
        self.hijos.append(concepto)
        return concepto

    def clonar_en(self, destino: "Agrupador") -> "Agrupador":
        """RF-05 video 5 / RF-02 video 8: clonación masiva de ramas WBS
        (equivalente al drag & drop entre proyectos)."""
        copia = destino.agregar_agrupador(self.clave, self.descripcion)
        for hijo in self.hijos:
            if isinstance(hijo, Agrupador):
                hijo.clonar_en(copia)
            else:
                copia.agregar_concepto(Concepto(
                    clave=hijo.clave, descripcion=hijo.descripcion,
                    unidad=hijo.unidad, cantidad=hijo.cantidad,
                    matriz=hijo.matriz, generador=hijo.generador))
        return copia

    def eliminar(self, clave: str) -> None:
        """RF-07 video 5: borrado en cascada (el subárbol completo se va
        con el nodo — integridad referencial)."""
        self.hijos = [h for h in self.hijos if h.clave != clave]

    # -- niveles (RF-06 video 5) ----------------------------------------
    @property
    def nivel(self) -> int:
        nivel, nodo = 0, self.padre
        while nodo is not None:
            nivel += 1
            nodo = nodo.padre
        return nivel

    def subir_nivel(self) -> None:
        """Desindentar: el nodo pasa a ser hermano de su padre."""
        padre = self.padre
        if padre is None or padre.padre is None:
            raise ValueError("El nodo ya está en el nivel máximo.")
        abuelo = padre.padre
        padre.hijos.remove(self)
        posicion = abuelo.hijos.index(padre) + 1
        abuelo.hijos.insert(posicion, self)
        self.padre = abuelo

    def bajar_nivel(self) -> None:
        """Indentar: el nodo pasa a ser hijo de su hermano anterior."""
        padre = self.padre
        if padre is None:
            raise ValueError("La raíz no puede cambiar de nivel.")
        indice = padre.hijos.index(self)
        anterior = next(
            (h for h in reversed(padre.hijos[:indice]) if isinstance(h, Agrupador)),
            None)
        if anterior is None:
            raise ValueError("No hay agrupador hermano anterior para anidar.")
        padre.hijos.remove(self)
        anterior.hijos.append(self)
        self.padre = anterior

    # -- consultas -------------------------------------------------------
    def iter_conceptos(self) -> Iterator[Concepto]:
        for hijo in self.hijos:
            if isinstance(hijo, Agrupador):
                yield from hijo.iter_conceptos()
            else:
                yield hijo

    def iter_nodos(self, nivel_maximo: int | None = None) -> Iterator[tuple[int, Union["Agrupador", Concepto]]]:
        """Recorrido jerárquico con filtro de nivel (RF-06 video 5:
        "Mostrar nivel N")."""
        for hijo in self.hijos:
            nivel = self.nivel + 1
            if nivel_maximo is not None and nivel > nivel_maximo:
                continue
            yield nivel, hijo
            if isinstance(hijo, Agrupador):
                yield from hijo.iter_nodos(nivel_maximo)

    def importe(self, ctx: "ContextoCalculo",
                con_sobrecostos: bool = True) -> Decimal:
        total = Decimal(0)
        for concepto in self.iter_conceptos():
            pu = concepto.costo_directo_unitario(ctx)
            if con_sobrecostos:
                pu = ctx.precio_venta(pu)
            total += ctx.precision.moneda(pu) * concepto.cantidad_efectiva
        return ctx.precision.moneda(total)


class ContextoCalculo:
    """Interfaz mínima que los recursos necesitan para valuarse.

    La implementa :class:`invar_calculator.proyecto.Proyecto`; se define
    aquí para pruebas unitarias aisladas.
    """

    def __init__(self, precision: ConfiguracionPrecision | None = None,
                 monedas=None, fsr: Callable[[Decimal], Decimal] | None = None,
                 precio_venta: Callable[[Decimal], Decimal] | None = None) -> None:
        from .moneda import SistemaMonedas

        self.precision = precision or ConfiguracionPrecision()
        self.monedas = monedas or SistemaMonedas()
        self._fsr = fsr or (lambda salario: Decimal(1))
        self._precio_venta = precio_venta or (lambda pu: pu)

    def fsr_factor(self, salario_base: Decimal) -> Decimal:
        return self._fsr(salario_base)

    def precio_venta(self, costo_directo: Decimal) -> Decimal:
        return self._precio_venta(costo_directo)
