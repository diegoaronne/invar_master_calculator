import unittest
from decimal import Decimal

from invar_calculator import (BaseCalculo, CalculoIndirectos,
                              CalculoUtilidad, GastoIndirecto,
                              MetodoOficinaCentral, ModoPie,
                              PersonalIndirecto, PiePrecios, Zona)


class TestPiePrecios(unittest.TestCase):
    def test_base_acumulable(self):
        """RF-02 video 28: cada cargo sobre la suma acumulada."""
        pie = PiePrecios()
        pie.agregar("A", "Cargo A", 10)
        pie.agregar("B", "Cargo B", 10)
        detalle = pie.aplicar(100)
        self.assertEqual(detalle.renglones[0].importe, Decimal("10.00"))
        self.assertEqual(detalle.renglones[1].base, Decimal("110.00"))
        self.assertEqual(detalle.precio_venta, Decimal("121.00"))

    def test_base_directa(self):
        pie = PiePrecios()
        pie.agregar("A", "Cargo A", 10, base=BaseCalculo.DIRECTO)
        pie.agregar("B", "Cargo B", 10, base=BaseCalculo.DIRECTO)
        self.assertEqual(pie.precio_venta(100), Decimal("120.00"))

    def test_modo_avanzado_formulas(self):
        """RF-01/RNF-02 video 28: fórmulas con variables CD y cargos previos."""
        pie = PiePrecios(modo=ModoPie.AVANZADO)
        pie.agregar("IND", "Indirectos", formula="CD*0.10")
        pie.agregar("EXTRA", "Extra ligado a indirectos", formula="IND*0.5")
        detalle = pie.aplicar(200)
        self.assertEqual(detalle.renglones[0].importe, Decimal("20.00"))
        self.assertEqual(detalle.renglones[1].importe, Decimal("10.00"))
        self.assertEqual(detalle.precio_venta, Decimal("230.00"))

    def test_identificador_duplicado(self):
        pie = PiePrecios()
        pie.agregar("A", "Cargo A", 10)
        with self.assertRaises(ValueError):
            pie.agregar("A", "Otro", 5)

    def test_plantilla_estandar(self):
        pie = PiePrecios.estandar_mexicano(
            indirectos_oficina=5, indirectos_campo=8,
            financiamiento=1, utilidad=10, cargos_adicionales="0.5")
        ids = [c.identificador for c in pie.cargos]
        self.assertEqual(ids, ["IND_OF", "IND_CAMPO", "FIN", "UTIL", "ADIC"])
        factor = pie.aplicar(100).factor_sobrecosto
        self.assertGreater(factor, Decimal("1.24"))


class TestUtilidad(unittest.TestCase):
    def test_utilidad_bruta_desde_neta(self):
        """UB = UN / (1 - ISR - PTU): 6% neta con 30+10 -> 10% bruta."""
        calculo = CalculoUtilidad(isr_pct=30, ptu_pct=10, utilidad_neta_pct=6)
        self.assertEqual(calculo.utilidad_bruta_pct(), Decimal("10.0000"))

    def test_hoja_calculo(self):
        calculo = CalculoUtilidad(isr_pct=30, ptu_pct=10, utilidad_neta_pct=6)
        hoja = calculo.hoja_calculo()
        # neta = bruta - ISR - PTU
        neta = (hoja["Utilidad bruta requerida (%)"]
                - hoja["ISR sobre utilidad (%)"]
                - hoja["PTU sobre utilidad (%)"])
        self.assertEqual(neta, Decimal("6.0000"))

    def test_transferencia_al_pie(self):
        """RF-05 video 33: inyección directa al pie de precios."""
        pie = PiePrecios.estandar_mexicano()
        calculo = CalculoUtilidad(isr_pct=30, ptu_pct=10, utilidad_neta_pct=6)
        calculo.transferir_a_presupuesto(pie)
        self.assertEqual(pie.obtener("UTIL").porcentaje, Decimal("10.0000"))

    def test_gravamen_imposible(self):
        with self.assertRaises(ValueError):
            CalculoUtilidad(isr_pct=60, ptu_pct=40,
                            utilidad_neta_pct=6).utilidad_bruta_pct()


class TestIndirectos(unittest.TestCase):
    def fsr_unitario(self, salario):
        return Decimal(1)

    def test_metodo_detallado(self):
        """RF-03 video 29: plantillas de personal y gastos por zona."""
        calculo = CalculoIndirectos(
            metodo_oficina_central=MetodoOficinaCentral.DETALLADO)
        calculo.agregar_personal(PersonalIndirecto(
            "Gerente", 50_000, 10, zona=Zona.CENTRAL, usa_fsr=False))
        calculo.agregar_gasto(GastoIndirecto("Renta", 10_000, 10,
                                             zona=Zona.CENTRAL))
        calculo.agregar_personal(PersonalIndirecto(
            "Residente", 30_000, 10, zona=Zona.CAMPO, usa_fsr=False))
        resultado = calculo.aplicar(10_000_000, self.fsr_unitario)
        self.assertEqual(resultado["oficina_central"], Decimal("6.0000"))
        self.assertEqual(resultado["oficina_campo"], Decimal("3.0000"))

    def test_metodo_anualizado(self):
        """RF-02 video 29: gasto anual / ingresos anuales."""
        calculo = CalculoIndirectos(
            metodo_oficina_central=MetodoOficinaCentral.ANUALIZADO,
            gasto_anual_oficina=1_000_000, ingresos_anuales_obras=20_000_000)
        pct = calculo.porcentaje_oficina_central(0, self.fsr_unitario)
        self.assertEqual(pct, Decimal("5.0000"))

    def test_metodo_porcentaje(self):
        calculo = CalculoIndirectos(
            metodo_oficina_central=MetodoOficinaCentral.PORCENTAJE,
            porcentaje_gasto_total="4.5")
        pct = calculo.porcentaje_oficina_central(0, self.fsr_unitario)
        self.assertEqual(pct, Decimal("4.5000"))

    def test_personal_con_fsr(self):
        """RNF-02 video 29: FSR del catálogo o factor manual."""
        persona = PersonalIndirecto("Residente", 10_000, 2, usa_fsr=True)
        importe = persona.importe(lambda s: Decimal("1.5"))
        self.assertEqual(importe, Decimal("30000"))
        manual = PersonalIndirecto("Residente", 10_000, 2, fsr_manual="1.2")
        self.assertEqual(manual.importe(lambda s: Decimal("9")),
                         Decimal("24000.0"))

    def test_transferencia_al_pie(self):
        """RF-04 video 29: transferir al pie de precios unitarios."""
        pie = PiePrecios.estandar_mexicano()
        calculo = CalculoIndirectos(
            metodo_oficina_central=MetodoOficinaCentral.PORCENTAJE,
            porcentaje_gasto_total=5)
        calculo.agregar_gasto(GastoIndirecto("Campamento", 20_000, 5,
                                             zona=Zona.CAMPO))
        calculo.transferir_a(pie, 1_000_000, self.fsr_unitario)
        self.assertEqual(pie.obtener("IND_OF").porcentaje, Decimal("5.0000"))
        self.assertEqual(pie.obtener("IND_CAMPO").porcentaje,
                         Decimal("10.0000"))

    def test_desglose_personal_auditoria(self):
        calculo = CalculoIndirectos()
        calculo.agregar_personal(PersonalIndirecto(
            "Residente", 10_000, 3, usa_fsr=False))
        filas = calculo.desglose_personal(self.fsr_unitario)
        self.assertEqual(filas[0]["importe"], Decimal("30000.00"))


if __name__ == "__main__":
    unittest.main()
