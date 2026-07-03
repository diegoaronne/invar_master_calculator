import unittest
from decimal import Decimal

from invar_calculator import Concepto, NumerosGeneradores


class TestNumerosGeneradores(unittest.TestCase):
    def test_calculo_por_dimensiones(self):
        """RF-02 video 10: largo × ancho × alto × piezas."""
        generador = NumerosGeneradores()
        generador.agregar("Eje 1", largo=2, ancho=3, alto=4, piezas=2)
        self.assertEqual(generador.cantidad_total(), Decimal("48.0000"))

    def test_dimensiones_omitidas_valen_uno(self):
        generador = NumerosGeneradores()
        generador.agregar("Tramo A-B", largo="12.5", ancho=2)
        self.assertEqual(generador.cantidad_total(), Decimal("25.0000"))

    def test_cuantificacion_hibrida(self):
        """RF-04 video 10: mezclar datos externos con cuantificador."""
        generador = NumerosGeneradores()
        generador.agregar("Externo", cantidad_directa="10.5")
        generador.agregar("Interno", largo=2, ancho=2)
        self.assertEqual(generador.cantidad_total(), Decimal("14.5000"))

    def test_precision_decimal(self):
        """RNF-03 video 10: sin errores de redondeo binario."""
        generador = NumerosGeneradores()
        generador.agregar("Excavación", largo="10", ancho="1", alto="0.40")
        self.assertEqual(generador.cantidad_total(), Decimal("4.0000"))

    def test_actualiza_cantidad_del_concepto(self):
        """RNF-02 video 10: la cantidad del presupuesto se deriva del
        generador en cuanto está activo."""
        generador = NumerosGeneradores()
        generador.agregar("Eje 1", largo=5, ancho=2)
        concepto = Concepto("C1", "Excavación", "m3", cantidad=999,
                            generador=generador)
        self.assertEqual(concepto.cantidad_efectiva, Decimal("10.0000"))
        generador.agregar("Eje 2", largo=1, ancho=1)
        self.assertEqual(concepto.cantidad_efectiva, Decimal("11.0000"))
        # Trazabilidad de la medición (RF-03 video 10).
        self.assertEqual(generador.lineas[0].referencia, "Eje 1")


if __name__ == "__main__":
    unittest.main()
