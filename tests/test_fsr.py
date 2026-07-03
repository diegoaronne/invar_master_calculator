import unittest
from decimal import Decimal

from invar_calculator import (CalendarioLaboralAnual, ConfiguracionPrecision,
                              CuotaPatronal, HojaFSR, PrestacionesLey,
                              redondear)


def hoja_simple(**kwargs):
    """Hoja con una sola cuota del 10% para valores verificables a mano."""
    parametros = dict(
        salario_minimo_general=100,
        prima_riesgo_pct=0,
        isn_pct=0,
        incluir_isn=False,
        calendario=CalendarioLaboralAnual(
            domingos=52, dias_festivos=8, dias_vacaciones=10,
            dias_por_clima=0, dias_por_costumbre=0, dias_por_permisos=0),
        prestaciones=PrestacionesLey(
            dias_aguinaldo=15, dias_vacaciones=10, prima_vacacional="0.25"),
        cuotas=[CuotaPatronal("Cuota única", 10)],
    )
    parametros.update(kwargs)
    return HojaFSR(**parametros)


class TestFSR(unittest.TestCase):
    def test_dias_pagados_y_laborados(self):
        hoja = hoja_simple()
        # Tp = 365 + 15 aguinaldo + 10*0.25 prima vacacional = 382.5
        self.assertEqual(hoja.dias_pagados(), Decimal("382.5"))
        # Tl = 365 - 52 - 8 - 10 = 295
        self.assertEqual(hoja.dias_laborados(), Decimal("295"))

    def test_formula_legal(self):
        """FSR = Ps*(Tp/Tl) + Tp/Tl con Ps = 10%."""
        hoja = hoja_simple()
        esperado = redondear(
            Decimal("382.5") / Decimal("295") * Decimal("1.10"), 5)
        self.assertEqual(hoja.factor(500), esperado)

    def test_cuota_sobre_smg(self):
        """La cuota fija sobre SMG pesa más en salarios bajos."""
        hoja = hoja_simple(cuotas=[CuotaPatronal("Fija", 20, base="smg")])
        # salario 100 = SMG -> fracción 20%; salario 400 -> 5%
        self.assertEqual(hoja.fraccion_cuotas(100), Decimal("0.2"))
        self.assertEqual(hoja.fraccion_cuotas(400), Decimal("0.05"))
        self.assertGreater(hoja.factor(100), hoja.factor(400))

    def test_isn_configurable(self):
        """RNF-02 video 21: el ISN puede excluirse para evitar duplicidad."""
        con_isn = hoja_simple(isn_pct=3, incluir_isn=True)
        sin_isn = hoja_simple(isn_pct=3, incluir_isn=False)
        self.assertGreater(con_isn.factor(500), sin_isn.factor(500))

    def test_salario_real(self):
        hoja = hoja_simple()
        factor = hoja.factor(300)
        self.assertEqual(hoja.salario_real(300),
                         redondear(Decimal(300) * factor, 2))

    def test_dias_clima_aumentan_factor(self):
        """RF-02 video 21: días perdidos por clima suben el FSR."""
        base = hoja_simple()
        con_clima = hoja_simple(calendario=CalendarioLaboralAnual(
            domingos=52, dias_festivos=8, dias_vacaciones=10,
            dias_por_clima=12))
        self.assertGreater(con_clima.factor(500), base.factor(500))

    def test_reportes(self):
        """RF-05 video 21: reportes Factor PS y FSR."""
        hoja = hoja_simple(isn_pct=3, incluir_isn=True)
        factor_ps = hoja.reporte_factor_ps(500)
        self.assertIn("Impuesto Sobre Nómina (ISN)", factor_ps)
        self.assertIn("Total Ps (%)", factor_ps)
        reporte = hoja.reporte_fsr(500)
        self.assertEqual(reporte["FSR"], hoja.factor(500))

    def test_calendario_sin_dias_laborables(self):
        hoja = hoja_simple(calendario=CalendarioLaboralAnual(
            domingos=200, dias_festivos=100, dias_vacaciones=65))
        with self.assertRaises(ValueError):
            hoja.factor(500)


if __name__ == "__main__":
    unittest.main()
