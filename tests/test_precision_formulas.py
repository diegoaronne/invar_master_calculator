import unittest
from decimal import Decimal

from invar_calculator import ConfiguracionPrecision, D, evaluar_formula, redondear
from invar_calculator.formulas import FormulaInvalida


class TestPrecision(unittest.TestCase):
    def test_conversion_decimal(self):
        self.assertEqual(D(0.1), Decimal("0.1"))
        self.assertEqual(D("2.5"), Decimal("2.5"))
        self.assertEqual(D(3), Decimal(3))

    def test_redondeo_configurable(self):
        self.assertEqual(redondear("1.234567", 5), Decimal("1.23457"))
        self.assertEqual(redondear("1.235", 2), Decimal("1.24"))  # half-up

    def test_precision_por_ambito(self):
        precision = ConfiguracionPrecision(costos=2, fsr=5)
        self.assertEqual(precision.moneda("10.005"), Decimal("10.01"))
        self.assertEqual(precision.factor("1.000005"), Decimal("1.00001"))


class TestFormulas(unittest.TestCase):
    def test_aritmetica_basica(self):
        self.assertEqual(evaluar_formula("2/20"), Decimal("0.1"))
        self.assertEqual(evaluar_formula("(1+2)*3"), Decimal(9))
        self.assertEqual(evaluar_formula("-4/2"), Decimal(-2))

    def test_variables(self):
        self.assertEqual(evaluar_formula("costo*1.1", {"costo": 100}),
                         Decimal("110.0"))

    def test_variable_desconocida(self):
        with self.assertRaises(FormulaInvalida):
            evaluar_formula("x+1")

    def test_codigo_no_permitido(self):
        with self.assertRaises(FormulaInvalida):
            evaluar_formula("__import__('os').system('id')")
        with self.assertRaises(FormulaInvalida):
            evaluar_formula("[1,2][0]")


if __name__ == "__main__":
    unittest.main()
