import datetime as dt
import unittest
from decimal import Decimal

from invar_calculator import (Concepto, DatosCostoHorario, DatosGenerales,
                              EscalaTiempo, ExplosionInsumos, Matriz,
                              Operador, ProgramaSuministros, Proyecto,
                              Recurso, TipoRecurso)

LUNES = dt.date(2026, 8, 3)


def proyecto_base() -> Proyecto:
    proyecto = Proyecto("Obra de prueba")
    cat = proyecto.catalogo
    cemento = cat.crear("CEM", descripcion="Cemento", unidad="ton", costo=2000)
    peon = cat.registrar(Recurso("PEON", "Peón", "jor",
                                 TipoRecurso.MANO_OBRA, salario_base=300,
                                 usa_fsr=False))
    herramienta = cat.registrar(Recurso("HERR", "Herramienta menor", "%mo",
                                        TipoRecurso.HERRAMIENTA))
    auxiliar = cat.registrar(Recurso("AUX", "Mortero", "m3",
                                     TipoRecurso.AUXILIAR))
    auxiliar.agregar_componente(cemento, "0.25")
    auxiliar.agregar_componente(peon, "0.5")

    matriz = proyecto.crear_matriz("MAT-MURO", "Muro", "m2")
    matriz.agregar_insumo(auxiliar, "0.04")
    matriz.agregar_insumo(peon, "0.2")
    matriz.agregar_insumo(herramienta, "0.03")

    grupo = proyecto.raiz.agregar_agrupador("01", "Albañilería")
    grupo.agregar_concepto(Concepto("C1", "Muro de block", "m2", 100,
                                    matriz=matriz))
    return proyecto


class TestExplosion(unittest.TestCase):
    def test_explosion_recursiva(self):
        """RF-01 video 22: llega hasta los recursos básicos."""
        proyecto = proyecto_base()
        lineas = ExplosionInsumos(proyecto).generar(proyecto.iter_conceptos())
        # Cemento: 100 * 0.04 * 0.25 = 1 ton
        self.assertEqual(lineas["CEM"].cantidad, Decimal("1.00"))
        self.assertEqual(lineas["CEM"].importe, Decimal("2000.00"))
        # Peón: 100 * (0.04*0.5 + 0.2) = 22 jor
        self.assertEqual(lineas["PEON"].cantidad, Decimal("22.00"))

    def test_filtro_por_tipo(self):
        """RF-02 video 22: solo los tipos seleccionados."""
        proyecto = proyecto_base()
        lineas = ExplosionInsumos(
            proyecto, tipos={TipoRecurso.MATERIAL}).generar(
                proyecto.iter_conceptos())
        self.assertIn("CEM", lineas)
        self.assertNotIn("PEON", lineas)
        self.assertNotIn("HERR", lineas)

    def test_herramienta_porcentaje_mo_en_explosion(self):
        proyecto = proyecto_base()
        lineas = ExplosionInsumos(proyecto).generar(proyecto.iter_conceptos())
        # %MO del nivel de la matriz: MO directa = 0.2*300 = 60 por m2;
        # importe herramienta = 100 * 0.03 * 60 = 180
        self.assertEqual(lineas["HERR"].importe, Decimal("180.00"))

    def test_indivisible_redondea_hacia_arriba(self):
        """RF-04 video 13: insumos indivisibles en enteros."""
        proyecto = Proyecto("Obra")
        pieza = proyecto.catalogo.crear("TAPA", descripcion="Tapa registro",
                                        unidad="pza", costo=150,
                                        indivisible=True)
        matriz = proyecto.crear_matriz("MAT-REG", "Registro", "pza")
        matriz.agregar_insumo(pieza, "1.1")
        proyecto.raiz.agregar_concepto(Concepto("C1", "Registros", "pza", 3,
                                                matriz=matriz))
        lineas = ExplosionInsumos(proyecto).generar(proyecto.iter_conceptos())
        # 3 * 1.1 = 3.3 -> 4 piezas
        self.assertEqual(lineas["TAPA"].cantidad, Decimal("4"))
        self.assertEqual(lineas["TAPA"].importe, Decimal("600.00"))

    def test_desglose_equipo(self):
        """RF-03 video 22: costo horario consolidado o desglosado."""
        proyecto = Proyecto("Obra")
        equipo = proyecto.catalogo.registrar(
            Recurso("EQ1", "Revolvedora", "hr", TipoRecurso.EQUIPO))
        equipo.datos_costo_horario = DatosCostoHorario(
            valor_adquisicion=50_000, porcentaje_rescate=10,
            vida_economica_anios=5, horas_por_anio=2000,
            tasa_interes_anual_pct=12, prima_seguro_anual_pct=2,
            potencia_hp=10, precio_combustible=24,
            operadores=[Operador("Op", 800)], horas_efectivas_turno=8)
        matriz = proyecto.crear_matriz("MAT-EQ", "Uso de equipo", "hr")
        matriz.agregar_insumo(equipo, 1)
        proyecto.raiz.agregar_concepto(
            Concepto("C1", "Trabajo con equipo", "hr", 10, matriz=matriz))

        consolidado = ExplosionInsumos(proyecto).generar(
            proyecto.iter_conceptos())
        self.assertIn("EQ1", consolidado)

        desglosado = ExplosionInsumos(proyecto, desglosar_equipo=True).generar(
            proyecto.iter_conceptos())
        self.assertNotIn("EQ1", desglosado)
        self.assertIn("EQ1.Depreciación", desglosado)
        self.assertIn("EQ1.Combustible", desglosado)
        self.assertIn("EQ1.Operación", desglosado)
        total_desglosado = sum((l.importe for l in desglosado.values()),
                               Decimal(0))
        total_consolidado = sum((l.importe for l in consolidado.values()),
                                Decimal(0))
        self.assertAlmostEqual(float(total_desglosado),
                               float(total_consolidado), places=1)

    def test_programa_suministros_cuadra_con_explosion(self):
        """RF-04 video 22: suministros por periodo = explosión total."""
        proyecto = proyecto_base()
        concepto = next(proyecto.iter_conceptos())
        proyecto.programa.programar(concepto, LUNES, 12)
        suministros = ProgramaSuministros(proyecto, proyecto.programa)
        datos = suministros.generar(EscalaTiempo.SEMANA, por="cantidad")
        self.assertEqual(sum(datos["CEM"].values()), Decimal("1.00"))
        self.assertEqual(sum(datos["PEON"].values()), Decimal("22.00"))
        self.assertGreater(len(datos["CEM"]), 1)  # varias semanas

    def test_suministros_por_monto(self):
        """RF-05 video 22: alternar cantidades y montos."""
        proyecto = proyecto_base()
        concepto = next(proyecto.iter_conceptos())
        proyecto.programa.programar(concepto, LUNES, 5)
        suministros = ProgramaSuministros(proyecto, proyecto.programa,
                                          tipos={TipoRecurso.MATERIAL})
        montos = suministros.generar(EscalaTiempo.MES, por="monto")
        self.assertEqual(sum(montos["CEM"].values()), Decimal("2000.00"))
        with self.assertRaises(ValueError):
            suministros.generar(EscalaTiempo.MES, por="otra_cosa")


class TestProyecto(unittest.TestCase):
    def test_nombre_maximo(self):
        """RF-01 video 1: nombre de hasta 128 caracteres."""
        Proyecto("x" * 128)
        with self.assertRaises(ValueError):
            Proyecto("x" * 129)
        with self.assertRaises(ValueError):
            Proyecto("")

    def test_recalcular_con_pie(self):
        """RF-04 video 28: recálculo tras cambiar sobrecostos."""
        proyecto = proyecto_base()
        antes = proyecto.recalcular()
        self.assertEqual(antes.costo_directo, antes.precio_venta)
        proyecto.pie.asignar_porcentaje("UTIL", 10)
        despues = proyecto.recalcular()
        self.assertEqual(despues.costo_directo, antes.costo_directo)
        self.assertGreater(despues.precio_venta, despues.costo_directo)
        self.assertEqual(despues.iva,
                         proyecto.precision.moneda(
                             despues.precio_venta * Decimal("0.16")))

    def test_matriz_reutilizable(self):
        """RF-06 video 4: una matriz vinculada a varios conceptos."""
        proyecto = proyecto_base()
        matriz = proyecto.crear_matriz("MAT-MURO")
        c2 = Concepto("C2", "Muro en otra partida", "m2", 50, matriz=matriz)
        proyecto.raiz.agregar_concepto(c2)
        self.assertIs(c2.matriz,
                      next(proyecto.iter_conceptos()).matriz)

    def test_validacion_duplicidad_isn(self):
        """RNF-02 video 21: alerta de ISN duplicado."""
        proyecto = proyecto_base()
        proyecto.hoja_fsr.incluir_isn = True
        proyecto.pie.obtener("ADIC").incluye_isn = True
        proyecto.pie.asignar_porcentaje("ADIC", 3)
        avisos = proyecto.validar()
        self.assertTrue(any("duplicidad de ISN" in a for a in avisos))

    def test_importe_por_agrupador(self):
        proyecto = proyecto_base()
        grupo = proyecto.raiz.hijos[0]
        importe = grupo.importe(proyecto, con_sobrecostos=False)
        self.assertEqual(importe, proyecto.costo_directo_total())


if __name__ == "__main__":
    unittest.main()
