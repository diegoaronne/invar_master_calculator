"""Construye el proyecto de demostración para el prototipo web.

Reutiliza exactamente la misma lógica que demo.py (motor probado), para que
cualquier persona que entre a la demo vea un presupuesto real y completo:
FSR, catálogo, matrices, WBS, calendario, indirectos y financiamiento.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import invar_calculator as ic

from .estado import EstadoSesion


def construir_estado_demo() -> EstadoSesion:
    """Proyecto demo + configuración de sobrecostos editable en el wizard."""
    proyecto = construir_proyecto_demo()
    estado = EstadoSesion(
        proyecto=proyecto,
        indirectos=_indirectos_demo(proyecto),
        financiamiento=ic.CalculoFinanciamiento(
            tasa_activa_anual_pct="14.5", tasa_pasiva_anual_pct="8.0",
            desfase_cobro_periodos=2, anticipo_pct=30,
            precision=proyecto.precision),
        utilidad=ic.CalculoUtilidad(isr_pct=30, ptu_pct=10,
                                    utilidad_neta_pct=6,
                                    precision=proyecto.precision),
        adicionales_pct="0.5",
    )
    estado.aplicar_sobrecostos()
    return estado


def construir_estado_vacio(nombre: str = "Proyecto nuevo") -> EstadoSesion:
    """Proyecto en blanco para capturar desde cero con el wizard."""
    return EstadoSesion(proyecto=ic.Proyecto(nombre))


def construir_proyecto_demo() -> ic.Proyecto:
    proyecto = ic.Proyecto(
        "Pavimentación de vialidad urbana — Etapa 1 (DEMO)",
        datos=ic.DatosGenerales(
            cliente="Municipio de Ejemplo",
            autor="INVAR Ingeniería",
            descripcion_obra="Pavimentación con concreto hidráulico",
            ubicacion="Estado de México",
            fecha_inicio=dt.date(2026, 8, 3),
            fecha_fin=dt.date(2026, 10, 31),
            responsables=["Ing. Responsable de Obra"],
        ),
    )

    proyecto.hoja_fsr = ic.HojaFSR(
        salario_minimo_general="278.80",
        anio_fiscal=2026,
        prima_riesgo_pct="7.58875",
        isn_pct="3.0",
        incluir_isn=True,
        calendario=ic.CalendarioLaboralAnual(dias_por_clima=8),
        precision=proyecto.precision,
    )

    cat = proyecto.catalogo
    cemento = cat.crear("CEM-01", descripcion="Cemento gris", unidad="ton",
                         costo=2850, familia="Cementantes")
    arena = cat.crear("ARE-01", descripcion="Arena de río", unidad="m3", costo=380)
    grava = cat.crear("GRA-01", descripcion="Grava 3/4", unidad="m3", costo=420)
    agua = cat.crear("AGU-01", descripcion="Agua", unidad="m3", costo=35)
    malla = cat.crear("MALLA-01", descripcion="Malla electrosoldada 6x6",
                       unidad="m2", costo=48, indivisible=False)

    peon = cat.registrar(ic.Recurso(
        "MO-PEON", "Peón", "jor", ic.TipoRecurso.MANO_OBRA, salario_base=310))
    oficial = cat.registrar(ic.Recurso(
        "MO-OFI", "Oficial albañil", "jor", ic.TipoRecurso.MANO_OBRA,
        salario_base=480))
    cabo = cat.registrar(ic.Recurso(
        "MO-CABO", "Cabo de oficios", "jor", ic.TipoRecurso.MANO_OBRA,
        salario_base=620))

    cuadrilla = cat.registrar(ic.Recurso(
        "CUAD-01", "Cuadrilla albañilería (1 oficial + 2 peones + cabo/10)",
        "jor", ic.TipoRecurso.MANO_OBRA))
    cuadrilla.agregar_componente(oficial, 1)
    cuadrilla.agregar_componente(peon, 2)
    cuadrilla.agregar_componente(cabo, "1/10")

    herramienta = cat.registrar(ic.Recurso(
        "HERR-01", "Herramienta menor", "%mo", ic.TipoRecurso.HERRAMIENTA))
    seguridad = cat.registrar(ic.Recurso(
        "EQSEG-01", "Equipo de seguridad", "%mo", ic.TipoRecurso.HERRAMIENTA))

    concreto = cat.registrar(ic.Recurso(
        "AUX-CONC200", "Concreto f'c=200 kg/cm2 hecho en obra", "m3",
        ic.TipoRecurso.AUXILIAR))
    concreto.agregar_componente(cemento, "0.35")
    concreto.agregar_componente(arena, "0.55")
    concreto.agregar_componente(grava, "0.65")
    concreto.agregar_componente(agua, "0.22")
    concreto.agregar_componente(cuadrilla, "0.10")

    operador = ic.Operador("Operador de revolvedora",
                            salario_real_turno=Decimal("980"), cantidad=1)
    revolvedora = cat.registrar(ic.Recurso(
        "EQ-REV01", "Revolvedora 1 saco 8HP", "hr", ic.TipoRecurso.EQUIPO))
    revolvedora.datos_costo_horario = ic.DatosCostoHorario(
        valor_adquisicion=68000, valor_llantas=4000,
        porcentaje_rescate=10, vida_economica_anios=4, horas_por_anio=1600,
        tasa_interes_anual_pct=14, prima_seguro_anual_pct=3,
        factor_mantenimiento="0.80",
        potencia_hp=8, factor_operacion="0.75",
        coeficiente_combustible="0.24", precio_combustible="24.50",
        capacidad_carter=2, horas_entre_cambios_aceite=100,
        precio_lubricante=95, vida_llantas_horas=2500,
        operadores=[operador], horas_efectivas_turno=8,
    )

    losa = proyecto.crear_matriz("MAT-LOSA", "Losa de concreto 15 cm", "m2")
    losa.agregar_insumo(concreto, "0.15")
    losa.agregar_insumo(malla, "1.05")
    losa.agregar_insumo(cuadrilla, "0.08")
    losa.agregar_insumo(revolvedora, "0.12")
    losa.agregar_insumo(herramienta, "0.03")
    losa.agregar_insumo(seguridad, "0.02")

    base = proyecto.crear_matriz("MAT-BASE", "Base hidráulica compactada", "m3")
    base.agregar_insumo(grava, "1.15")
    base.agregar_insumo(agua, "0.10")
    base.agregar_insumo(cuadrilla, "0.25")
    base.agregar_insumo(herramienta, "0.03")

    preliminar = proyecto.raiz.agregar_agrupador("01", "Preliminares")
    pavimento = proyecto.raiz.agregar_agrupador("02", "Pavimento")

    generador = ic.NumerosGeneradores(proyecto.precision)
    generador.agregar("Cuerpo A, Eje 1-4", largo=120, ancho="7.5", alto="0.20")
    generador.agregar("Cuerpo B, Eje 5-8", largo=95, ancho="7.5", alto="0.20")
    concepto_base = ic.Concepto("C-BASE", "Base hidráulica de 20 cm", "m3",
                                 matriz=base, generador=generador)
    preliminar.agregar_concepto(concepto_base)

    concepto_losa = ic.Concepto("C-LOSA", "Losa de concreto MR-42 de 15 cm",
                                 "m2", cantidad=1612, matriz=losa)
    pavimento.agregar_concepto(concepto_losa)

    proyecto.calendario.marcar(dt.date(2026, 9, 16), ic.EstadoDia.NO_TRABAJABLE)
    proyecto.calendario.marcar(dt.date(2026, 12, 24),
                                ic.EstadoDia.PERSONALIZADO, horas=5)

    act_base = proyecto.programa.programar(
        concepto_base, dt.date(2026, 8, 3), duracion_laborable=20)
    proyecto.programa.programar(
        concepto_losa, dt.date(2026, 8, 31), duracion_laborable=45,
        predecesoras=[act_base])
    proyecto.programa.sincronizar_fechas()
    return proyecto


def _indirectos_demo(proyecto: ic.Proyecto) -> ic.CalculoIndirectos:
    indirectos = ic.CalculoIndirectos(
        metodo_oficina_central=ic.MetodoOficinaCentral.ANUALIZADO,
        gasto_anual_oficina=1_800_000, ingresos_anuales_obras=32_000_000,
        duracion_obra_meses=3, precision=proyecto.precision)
    indirectos.agregar_personal(ic.PersonalIndirecto(
        "Superintendente de obra", 42_000, 3, zona=ic.Zona.CAMPO,
        categoria=ic.CategoriaPersonal.TECNICO, usa_fsr=False))
    indirectos.agregar_personal(ic.PersonalIndirecto(
        "Residente", 28_000, 3, zona=ic.Zona.CAMPO,
        categoria=ic.CategoriaPersonal.TECNICO, usa_fsr=False))
    indirectos.agregar_gasto(ic.GastoIndirecto(
        "Oficina de campo (renta y servicios)", 9_500, 3, zona=ic.Zona.CAMPO))
    return indirectos
