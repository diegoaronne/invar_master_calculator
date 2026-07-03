import unittest
from decimal import Decimal

from invar_calculator import EscalaTiempo, TipoRecurso
from invar_calculator.reportes import (Columna, Tabla, reporte_apu,
                                       reporte_explosion, reporte_fsr,
                                       reporte_financiamiento,
                                       reporte_pie_precios,
                                       reporte_presupuesto)
from invar_calculator import CalculoFinanciamiento

from tests.test_explosion_proyecto import proyecto_base


class TestTabla(unittest.TestCase):
    def test_render_y_csv(self):
        tabla = Tabla("Prueba", ["A", "B"])
        tabla.agregar_fila("x", Decimal("1234.50"))
        salida = tabla.render()
        self.assertIn("Prueba", salida)
        self.assertIn("1,234.50", salida)
        csv_texto = tabla.a_csv()
        self.assertIn("A,B", csv_texto)

    def test_columna_no_imprimible(self):
        """RF-04 video 34: columnas visibles para cálculo pero excluidas
        del reporte."""
        tabla = Tabla("Prueba", ["Clave", Columna("Interno", imprimible=False)])
        tabla.agregar_fila("C1", "secreto")
        self.assertNotIn("secreto", tabla.render())
        self.assertIn("secreto", tabla.render(solo_imprimibles=False))
        self.assertNotIn("secreto", tabla.a_csv())

    def test_fila_inconsistente(self):
        tabla = Tabla("Prueba", ["A"])
        with self.assertRaises(ValueError):
            tabla.agregar_fila("x", "y")


class TestReportes(unittest.TestCase):
    def setUp(self):
        self.proyecto = proyecto_base()

    def test_reporte_presupuesto(self):
        texto = reporte_presupuesto(self.proyecto).render()
        self.assertIn("C1", texto)
        self.assertIn("COSTO DIRECTO", texto)
        self.assertIn("TOTAL CON IVA", texto)

    def test_reporte_apu(self):
        concepto = next(self.proyecto.iter_conceptos())
        texto = reporte_apu(self.proyecto, concepto).render()
        self.assertIn("PRECIO UNITARIO DE VENTA", texto)
        self.assertIn("AUX", texto)

    def test_reporte_fsr(self):
        texto = reporte_fsr(self.proyecto, 300).render()
        self.assertIn("FSR", texto)
        self.assertIn("Total Ps (%)", texto)

    def test_reporte_explosion(self):
        texto = reporte_explosion(self.proyecto,
                                  tipos={TipoRecurso.MATERIAL}).render()
        self.assertIn("CEM", texto)
        self.assertNotIn("PEON", texto)

    def test_reporte_financiamiento_formatos(self):
        """RF-01 video 32: formatos horizontal y vertical."""
        calculo = CalculoFinanciamiento(
            tasa_activa_anual_pct=12, tasa_pasiva_anual_pct=12,
            desfase_cobro_periodos=1, anticipo_pct=30)
        resultado = calculo.calcular([100, 100])
        horizontal = reporte_financiamiento(resultado, "horizontal")
        vertical = reporte_financiamiento(resultado, "vertical")
        self.assertIn("Egresos", horizontal.render())
        self.assertIn("% Financiamiento", vertical.render())
        with self.assertRaises(ValueError):
            reporte_financiamiento(resultado, "diagonal")

    def test_reporte_pie(self):
        self.proyecto.pie.asignar_porcentaje("UTIL", 10)
        texto = reporte_pie_precios(self.proyecto).render()
        self.assertIn("Utilidad", texto)
        self.assertIn("PRECIO DE VENTA", texto)


if __name__ == "__main__":
    unittest.main()
