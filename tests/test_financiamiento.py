import unittest
from decimal import Decimal

from invar_calculator import (BaseAnticipo, CalculoFinanciamiento,
                              ErrorPrecondicion, PiePrecios)


class TestFinanciamiento(unittest.TestCase):
    def test_precondicion_programa(self):
        """RNF-01 video 32: sin programa de egresos no hay cálculo."""
        calculo = CalculoFinanciamiento()
        with self.assertRaises(ErrorPrecondicion):
            calculo.calcular([])
        with self.assertRaises(ErrorPrecondicion):
            calculo.calcular([0, 0])

    def test_flujo_verificable_a_mano(self):
        """Anticipo 30% de 200 = 60 en el periodo 1; estimaciones netas
        de amortización (70) cobradas con un periodo de desfase; tasas
        12% anual = 1% mensual."""
        calculo = CalculoFinanciamiento(
            tasa_activa_anual_pct=12, tasa_pasiva_anual_pct=12,
            desfase_cobro_periodos=1, anticipo_pct=30)
        resultado = calculo.calcular([100, 100])
        r = resultado.renglones
        self.assertEqual(r[0].ingreso, Decimal("60.00"))
        self.assertEqual(r[0].saldo, Decimal("-40.00"))
        self.assertEqual(r[0].interes, Decimal("-0.40"))
        self.assertEqual(r[1].ingreso, Decimal("70.00"))
        self.assertEqual(r[1].saldo, Decimal("-70.00"))
        self.assertEqual(r[1].interes, Decimal("-0.70"))
        self.assertEqual(r[2].saldo, Decimal("0.00"))
        self.assertEqual(resultado.total_intereses, Decimal("-1.10"))
        # % = 1.10 / 200 * 100
        self.assertEqual(resultado.porcentaje_financiamiento,
                         Decimal("0.5500"))

    def test_los_ingresos_cubren_los_egresos(self):
        """El anticipo se amortiza por completo: Σingresos = Σegresos."""
        calculo = CalculoFinanciamiento(desfase_cobro_periodos=2,
                                        anticipo_pct=30)
        resultado = calculo.calcular([120, 200, 80])
        ingresos = sum(r.ingreso for r in resultado.renglones)
        self.assertEqual(ingresos, Decimal("400.00"))
        self.assertEqual(resultado.renglones[-1].saldo, Decimal("0.00"))

    def test_anticipo_sobre_materiales(self):
        """RF-04 video 32: anticipo sobre el monto de materiales."""
        calculo = CalculoFinanciamiento(
            anticipo_pct=10, base_anticipo=BaseAnticipo.MATERIALES,
            monto_materiales=500, desfase_cobro_periodos=1)
        resultado = calculo.calcular([100, 100])
        self.assertEqual(resultado.renglones[0].ingreso, Decimal("50.00"))

    def test_anticipos_parciales(self):
        """RF-04 video 32: entrega del anticipo en varios periodos."""
        calculo = CalculoFinanciamiento(
            anticipo_pct=30, desfase_cobro_periodos=1,
            anticipos_parciales=[(0, 50), (1, 50)])
        resultado = calculo.calcular([100, 100])
        # 60 de anticipo repartido: 30 en periodo 1, 30 + 70 en periodo 2
        self.assertEqual(resultado.renglones[0].ingreso, Decimal("30.00"))
        self.assertEqual(resultado.renglones[1].ingreso, Decimal("100.00"))

    def test_saldo_positivo_gana_tasa_pasiva(self):
        """RF-03 video 32: tasa pasiva (a favor) sobre saldos positivos."""
        calculo = CalculoFinanciamiento(
            tasa_activa_anual_pct=24, tasa_pasiva_anual_pct=12,
            desfase_cobro_periodos=0, anticipo_pct=50)
        resultado = calculo.calcular([100, 100])
        self.assertGreater(resultado.renglones[0].interes, 0)

    def test_transferencia_al_pie(self):
        """RF-05 video 32: inyección del porcentaje al pie de precios."""
        pie = PiePrecios.estandar_mexicano()
        calculo = CalculoFinanciamiento(
            tasa_activa_anual_pct=12, tasa_pasiva_anual_pct=12,
            desfase_cobro_periodos=1, anticipo_pct=30)
        pct = calculo.transferir_a(pie, [100, 100])
        self.assertEqual(pie.obtener("FIN").porcentaje, pct)
        self.assertEqual(pct, Decimal("0.5500"))


if __name__ == "__main__":
    unittest.main()
