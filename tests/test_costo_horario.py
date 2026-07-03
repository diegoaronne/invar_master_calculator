import unittest
from decimal import Decimal

from invar_calculator import ConfiguracionPrecision, DatosCostoHorario, Operador


def datos_ejemplo(**kwargs):
    parametros = dict(
        valor_adquisicion=100_000,
        valor_llantas=10_000,
        porcentaje_rescate=10,
        vida_economica_anios=5,
        horas_por_anio=2000,
        tasa_interes_anual_pct=12,
        prima_seguro_anual_pct=3,
        factor_mantenimiento="0.80",
        potencia_hp=100,
        factor_operacion="0.80",
        coeficiente_combustible="0.20",
        precio_combustible=25,
        capacidad_carter=10,
        horas_entre_cambios_aceite=100,
        precio_lubricante=90,
        vida_llantas_horas=5000,
        operadores=[Operador("Operador", salario_real_turno=800)],
        horas_efectivas_turno=8,
    )
    parametros.update(kwargs)
    return DatosCostoHorario(**parametros)


class TestCostoHorario(unittest.TestCase):
    def test_cargos_fijos(self):
        """Va = 100000-10000 = 90000; Vr = 9000; Ve = 10000 h."""
        fijos = datos_ejemplo().cargos_fijos()
        self.assertEqual(fijos["Depreciación"], Decimal("8.1"))
        # I = (99000 / (2*2000)) * 0.12 = 2.97
        self.assertEqual(fijos["Inversión"], Decimal("2.97"))
        self.assertEqual(fijos["Seguros"], Decimal("0.7425"))
        # M = 0.8 * 8.1
        self.assertEqual(fijos["Mantenimiento"], Decimal("6.48"))

    def test_cargos_consumo(self):
        consumos = datos_ejemplo().cargos_consumo()
        # 0.20 * 100 HP * 0.80 = 16 lt/h * $25 = 400
        self.assertEqual(consumos["Combustible"], Decimal("400.00"))
        # 10/100 = 0.1 lt/h * $90 = 9
        self.assertEqual(consumos["Lubricantes"], Decimal("9.0"))
        # 10000 / 5000 h = 2
        self.assertEqual(consumos["Llantas"], Decimal("2"))

    def test_cargo_operacion(self):
        operacion = datos_ejemplo().cargos_operacion()
        self.assertEqual(operacion["Operación"], Decimal("100"))

    def test_costo_horario_total(self):
        total = datos_ejemplo().costo_horario(ConfiguracionPrecision())
        # 8.1 + 2.97 + 0.7425 + 6.48 + 400 + 9 + 2 + 0 + 100
        self.assertEqual(total, Decimal("529.2925"))

    def test_modo_manual(self):
        """RF-01 video 16: la captura manual reemplaza a las fórmulas."""
        datos = datos_ejemplo(calculo_manual=True,
                              combustible_manual="350",
                              lubricante_manual="7.5",
                              llantas_manual="1.8",
                              operacion_manual="95")
        consumos = datos.cargos_consumo()
        self.assertEqual(consumos["Combustible"], Decimal("350"))
        self.assertEqual(consumos["Lubricantes"], Decimal("7.5"))
        self.assertEqual(consumos["Llantas"], Decimal("1.8"))
        self.assertEqual(datos.cargos_operacion()["Operación"], Decimal("95"))

    def test_coeficiente_modificable(self):
        """RNF-02 video 16: los factores técnicos pueden romperse."""
        datos = datos_ejemplo(coeficiente_combustible="0.1514")
        combustible = datos.cargos_consumo()["Combustible"]
        self.assertEqual(combustible,
                         Decimal("0.1514") * 100 * Decimal("0.80") * 25)

    def test_desglose_para_auditoria(self):
        """RNF-02 video 15: transparencia del cálculo."""
        desglose = datos_ejemplo().desglose(ConfiguracionPrecision())
        self.assertIn("Cargos fijos", desglose)
        self.assertIn("Cargos por consumo", desglose)
        self.assertIn("Cargos por operación", desglose)

    def test_vida_economica_invalida(self):
        with self.assertRaises(ValueError):
            datos_ejemplo(vida_economica_anios=0).cargos_fijos()


if __name__ == "__main__":
    unittest.main()
