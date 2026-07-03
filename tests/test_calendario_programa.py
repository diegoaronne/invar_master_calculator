import datetime as dt
import unittest
from decimal import Decimal

from invar_calculator import (CalendarioTrabajo, Concepto, ContextoCalculo,
                              EscalaTiempo, EstadoDia, Matriz, ProgramaObra,
                              Recurso)

LUNES = dt.date(2026, 8, 3)


class TestCalendario(unittest.TestCase):
    def setUp(self):
        self.cal = CalendarioTrabajo(horas_jornada=8)

    def test_estados_por_defecto(self):
        """RF-01 video 24: trabajable 8h, sábado medio, domingo cero."""
        self.assertEqual(self.cal.horas(LUNES), Decimal(8))
        sabado = dt.date(2026, 8, 8)
        domingo = dt.date(2026, 8, 9)
        self.assertEqual(self.cal.horas(sabado), Decimal(4))
        self.assertEqual(self.cal.horas(domingo), Decimal(0))
        self.assertFalse(self.cal.es_laborable(domingo))

    def test_jornada_personalizada_en_fecha(self):
        """RF-03 video 24: p. ej. 5 horas el 24 de diciembre."""
        nochebuena = dt.date(2026, 12, 24)
        self.cal.marcar(nochebuena, EstadoDia.PERSONALIZADO, horas=5)
        self.assertEqual(self.cal.horas(nochebuena), Decimal(5))
        with self.assertRaises(ValueError):
            self.cal.marcar(nochebuena, EstadoDia.PERSONALIZADO)

    def test_marcar_festivo(self):
        """RF-02 video 24: interacción directa con fechas."""
        festivo = dt.date(2026, 9, 16)
        self.cal.marcar(festivo, EstadoDia.NO_TRABAJABLE)
        self.assertFalse(self.cal.es_laborable(festivo))

    def test_regla_semanal(self):
        self.cal.configurar_dia_semana(5, EstadoDia.NO_TRABAJABLE)
        self.assertFalse(self.cal.es_laborable(dt.date(2026, 8, 8)))

    def test_sumar_laborables(self):
        """RNF-01 video 24: el calendario restringe el cálculo de fechas."""
        # 6 días laborables desde el lunes: lun-vie + sábado.
        fin = self.cal.sumar_laborables(LUNES, 6)
        self.assertEqual(fin, dt.date(2026, 8, 8))
        # 7 días saltan el domingo.
        fin = self.cal.sumar_laborables(LUNES, 7)
        self.assertEqual(fin, dt.date(2026, 8, 10))

    def test_contar_laborables(self):
        """RF-01 video 26: auditoría de días trabajables."""
        cuenta = self.cal.contar_laborables(LUNES, dt.date(2026, 8, 9))
        self.assertEqual(cuenta, 6)


class TestPrograma(unittest.TestCase):
    def setUp(self):
        self.ctx = ContextoCalculo()
        self.programa = ProgramaObra(
            CalendarioTrabajo(),
            fecha_inicio_proyecto=LUNES,
            fecha_fin_proyecto=dt.date(2026, 12, 31))
        material = Recurso("MAT", costo=10)
        self.matriz = Matriz("M1")
        self.matriz.agregar_insumo(material, 1)
        self.concepto_a = Concepto("A", "Actividad A", "m2", 100,
                                   matriz=self.matriz)
        self.concepto_b = Concepto("B", "Actividad B", "m2", 50,
                                   matriz=self.matriz)
        self.concepto_c = Concepto("C", "Actividad C", "m2", 80,
                                   matriz=self.matriz)

    def test_fechas_y_auditoria(self):
        actividad = self.programa.programar(self.concepto_a, LUNES, 6)
        datos = self.programa.auditoria(actividad)
        self.assertEqual(datos["inicio"], LUNES)
        self.assertEqual(datos["fin"], dt.date(2026, 8, 8))
        self.assertEqual(datos["dias_trabajables"], 6)
        self.assertEqual(datos["dias_calendario"], 6)

    def test_alerta_fuera_de_rango(self):
        """RNF-01 video 26: alerta por desfase temporal."""
        self.programa.programar(self.concepto_a,
                                LUNES - dt.timedelta(days=7), 5)
        self.assertTrue(any("antes del inicio" in a
                            for a in self.programa.alertas))

    def test_sincronizar_fechas(self):
        """RF-02 video 26: proyecto vs programa con sincronización."""
        self.programa.programar(self.concepto_a, LUNES, 5)
        self.programa.sincronizar_fechas()
        inicio, fin = self.programa.fechas_programa()
        self.assertEqual(self.programa.fecha_inicio_proyecto, inicio)
        self.assertEqual(self.programa.fecha_fin_proyecto, fin)

    def test_fraccionamiento(self):
        """RF-04 video 26: cantidad distribuida en etapas."""
        actividad = self.programa.programar(self.concepto_a, LUNES, 5,
                                            porcentaje=60)
        actividad.agregar_segmento(dt.date(2026, 9, 7), 5, porcentaje=40)
        self.assertEqual(actividad.porcentaje_programado(), Decimal(100))
        self.assertEqual(self.programa.validar_fraccionamiento(), [])
        reparto = self.programa.distribuir_actividad(
            actividad, EscalaTiempo.MES, 100)
        self.assertEqual(sum(reparto.values()), Decimal(100))
        self.assertEqual(reparto["2026-08"], Decimal(60))
        self.assertEqual(reparto["2026-09"], Decimal(40))

    def test_fraccionamiento_incompleto_avisa(self):
        self.programa.programar(self.concepto_a, LUNES, 5, porcentaje=70)
        avisos = self.programa.validar_fraccionamiento()
        self.assertEqual(len(avisos), 1)

    def test_ruta_critica(self):
        """RF-04 video 23: CPM identifica la cadena sin holgura."""
        a = self.programa.programar(self.concepto_a, LUNES, 5)
        b = self.programa.programar(self.concepto_b, LUNES, 3,
                                    predecesoras=[a])
        c = self.programa.programar(self.concepto_c, LUNES, 10)
        datos = self.programa.ruta_critica()
        self.assertTrue(datos[c].es_critica)
        self.assertEqual(datos[a].holgura, 2)
        self.assertEqual(datos[b].holgura, 2)
        criticas = self.programa.actividades_criticas()
        self.assertEqual(criticas, [c])

    def test_dependencia_circular(self):
        a = self.programa.programar(self.concepto_a, LUNES, 5)
        b = self.programa.programar(self.concepto_b, LUNES, 3,
                                    predecesoras=[a])
        a.predecesoras = [b]
        with self.assertRaises(ValueError):
            self.programa.ruta_critica()

    def test_programa_cantidades_y_montos(self):
        """RF-03 video 23: vistas por cantidades y por montos."""
        self.programa.programar(self.concepto_a, LUNES, 5)
        cantidades = self.programa.programa_cantidades(EscalaTiempo.SEMANA)
        self.assertEqual(sum(cantidades["A"].values()), Decimal(100))
        montos = self.programa.programa_montos(EscalaTiempo.SEMANA, self.ctx,
                                               con_sobrecostos=False)
        self.assertEqual(sum(montos.values()), Decimal(1000))

    def test_distribucion_pondera_por_horas(self):
        """El sábado (media jornada) recibe la mitad de carga."""
        actividad = self.programa.programar(self.concepto_a, LUNES, 6)
        reparto = self.programa.distribuir_actividad(
            actividad, EscalaTiempo.DIA, 44)
        from invar_calculator import redondear
        self.assertEqual(redondear(reparto["2026-08-03"], 6), Decimal(8))
        self.assertEqual(redondear(reparto["2026-08-08"], 6), Decimal(4))
        self.assertEqual(redondear(sum(reparto.values()), 6), Decimal(44))


if __name__ == "__main__":
    unittest.main()
