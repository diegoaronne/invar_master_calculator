import unittest
from decimal import Decimal

from invar_calculator import (Agrupador, Catalogo, Concepto, ContextoCalculo,
                              ErrorReferenciaCircular, Matriz, Moneda, Recurso,
                              SistemaMonedas, TipoRecurso)


def ctx(**kwargs):
    return ContextoCalculo(**kwargs)


class TestCatalogo(unittest.TestCase):
    def setUp(self):
        self.catalogo = Catalogo()

    def test_registro_vincula_existente(self):
        """RNF-02 video 13: clave repetida vincula, no duplica."""
        original = self.catalogo.crear("CEM", descripcion="Cemento", costo=100)
        duplicado = self.catalogo.registrar(Recurso("CEM", "Otro", costo=999))
        self.assertIs(duplicado, original)
        self.assertEqual(len(self.catalogo), 1)

    def test_busqueda_comodines(self):
        self.catalogo.crear("PIN-01", descripcion="Pintura vinílica")
        self.catalogo.crear("TEP-01", descripcion="Acarreo de tepetate")
        self.assertEqual(len(self.catalogo.buscar("*tepetate")), 1)
        self.assertEqual(len(self.catalogo.buscar("pintura")), 1)
        self.assertEqual(len(self.catalogo.buscar("ZZZ")), 0)

    def test_homologacion(self):
        """RF-03 video 20: fusionar duplicados actualiza referencias."""
        maestro = self.catalogo.crear("ARE-01", descripcion="Arena", costo=380)
        duplicado = self.catalogo.crear("ARENA", descripcion="Arena río", costo=400)
        matriz = Matriz("MAT-1")
        matriz.agregar_insumo(duplicado, 2)
        self.catalogo.registrar(matriz)
        self.catalogo.homologar(["ARENA"], "ARE-01")
        self.assertIs(matriz.insumos[0].recurso, maestro)
        self.assertNotIn("ARENA", self.catalogo)

    def test_donde_participa(self):
        arena = self.catalogo.crear("ARE", costo=1)
        auxiliar = self.catalogo.registrar(
            Recurso("AUX", tipo=TipoRecurso.AUXILIAR))
        auxiliar.agregar_componente(arena, 1)
        matriz = Matriz("MAT")
        matriz.agregar_insumo(auxiliar, 1)
        self.catalogo.registrar(matriz)
        recursivo = {r.clave for r in self.catalogo.donde_participa("ARE")}
        directo = {r.clave for r in self.catalogo.donde_participa(
            "ARE", recursivo=False)}
        self.assertEqual(recursivo, {"AUX", "MAT"})
        self.assertEqual(directo, {"AUX"})

    def test_cambiar_tipo(self):
        """RF-05 video 20: conversión de naturaleza."""
        recurso = self.catalogo.crear("X", tipo=TipoRecurso.MATERIAL)
        self.catalogo.cambiar_tipo("X", TipoRecurso.MANO_OBRA)
        self.assertEqual(recurso.tipo, TipoRecurso.MANO_OBRA)


class TestMatriz(unittest.TestCase):
    def test_costo_compuesto_y_formula_cantidad(self):
        """Cuadrilla con mando proporcional 1/10 (RF-04 video 14)."""
        contexto = ctx()
        oficial = Recurso("OF", tipo=TipoRecurso.MANO_OBRA, salario_base=400,
                          usa_fsr=False)
        cabo = Recurso("CABO", tipo=TipoRecurso.MANO_OBRA, salario_base=600,
                       usa_fsr=False)
        cuadrilla = Recurso("CUAD", tipo=TipoRecurso.MANO_OBRA)
        cuadrilla.agregar_componente(oficial, 1)
        cuadrilla.agregar_componente(cabo, "1/10")
        self.assertEqual(cuadrilla.costo_unitario(contexto), Decimal("460.00"))

    def test_herramienta_porcentaje_mo(self):
        """RF-01/RF-02 video 17: %MO se calcula sobre la mano de obra."""
        contexto = ctx()
        peon = Recurso("PEON", tipo=TipoRecurso.MANO_OBRA, salario_base=300,
                       usa_fsr=False)
        material = Recurso("MAT", costo=100)
        herramienta = Recurso("HERR", tipo=TipoRecurso.HERRAMIENTA)
        matriz = Matriz("M1")
        matriz.agregar_insumo(peon, 2)        # MO = 600
        matriz.agregar_insumo(material, 1)    # 100
        matriz.agregar_insumo(herramienta, "0.03")  # 3% de 600 = 18
        self.assertEqual(matriz.costo_unitario(contexto), Decimal("718.00"))

    def test_referencia_circular(self):
        """RNF-03 video 12/18: prohibido el ciclo directo e indirecto."""
        a = Recurso("A", tipo=TipoRecurso.AUXILIAR)
        b = Recurso("B", tipo=TipoRecurso.AUXILIAR)
        a.agregar_componente(b, 1)
        with self.assertRaises(ErrorReferenciaCircular):
            b.agregar_componente(a, 1)
        with self.assertRaises(ErrorReferenciaCircular):
            a.agregar_componente(a, 1)

    def test_copiar_desglose(self):
        """RF-03/RF-04 video 25: copiar solo el desglose con resolución
        de conflictos."""
        contexto = ctx()
        arena_local = Recurso("ARE", costo=100)
        arena_fuente = Recurso("ARE", costo=999)
        cal = Recurso("CAL", costo=50)
        destino = Matriz("DEST")
        destino.agregar_insumo(arena_local, 1)
        fuente = Matriz("FUENTE")
        fuente.agregar_insumo(arena_fuente, 2)
        fuente.agregar_insumo(cal, 1)
        destino.copiar_desglose_desde(fuente, reemplazar_existentes=True)
        self.assertEqual(destino.costo_unitario(contexto),
                         Decimal("2048.00"))  # 2*999 + 50
        destino2 = Matriz("DEST2")
        destino2.agregar_insumo(arena_local, 1)
        destino2.copiar_desglose_desde(fuente, reemplazar_existentes=False)
        self.assertEqual(destino2.costo_unitario(contexto),
                         Decimal("150.00"))  # conserva 1*100 + 50

    def test_resumen_por_tipo(self):
        contexto = ctx()
        peon = Recurso("PEON", tipo=TipoRecurso.MANO_OBRA, salario_base=300,
                       usa_fsr=False)
        material = Recurso("MAT", costo=100)
        matriz = Matriz("M1")
        matriz.agregar_insumo(peon, 1)
        matriz.agregar_insumo(material, 2)
        resumen = matriz.resumen_por_tipo(contexto)
        self.assertEqual(resumen["Mano de obra"], Decimal("300.00"))
        self.assertEqual(resumen["Material"], Decimal("200.00"))
        self.assertEqual(resumen["Total"], Decimal("500.00"))


class TestMultimoneda(unittest.TestCase):
    def test_conversion_a_base(self):
        """RF-02 video 2: multimoneda con tipo de cambio."""
        monedas = SistemaMonedas()
        monedas.registrar(Moneda("USD", "Dólar", "US$", tipo_cambio="17.50"))
        contexto = ctx(monedas=monedas)
        bomba = Recurso("BOMBA", costo=100, moneda="USD")
        self.assertEqual(bomba.costo_unitario(contexto), Decimal("1750.00"))
        self.assertTrue(monedas.multimoneda)


class TestWBS(unittest.TestCase):
    def setUp(self):
        self.raiz = Agrupador("", "Presupuesto")
        self.cap1 = self.raiz.agregar_agrupador("01", "Preliminares")
        self.sub = self.cap1.agregar_agrupador("01.01", "Trazo")
        self.concepto = self.sub.agregar_concepto(
            Concepto("C1", "Limpieza", "m2", 10))

    def test_niveles_ilimitados(self):
        self.assertEqual(self.cap1.nivel, 1)
        self.assertEqual(self.sub.nivel, 2)

    def test_eliminacion_cascada(self):
        """RF-07 video 5: al borrar el padre se van los hijos."""
        self.raiz.eliminar("01")
        self.assertEqual(list(self.raiz.iter_conceptos()), [])

    def test_clonacion_estructura(self):
        """RF-05 video 5 / RF-02 video 8: clonado de ramas completas."""
        destino = Agrupador("", "Otro proyecto")
        self.cap1.clonar_en(destino)
        conceptos = list(destino.iter_conceptos())
        self.assertEqual(len(conceptos), 1)
        self.assertEqual(conceptos[0].clave, "C1")
        self.assertIsNot(conceptos[0], self.concepto)

    def test_subir_bajar_nivel(self):
        """RF-06 video 5: indentar y desindentar nodos."""
        self.sub.subir_nivel()
        self.assertEqual(self.sub.nivel, 1)
        self.sub.bajar_nivel()
        self.assertEqual(self.sub.nivel, 2)
        self.assertIs(self.sub.padre, self.cap1)

    def test_filtro_por_nivel(self):
        nodos_n1 = [n for _, n in self.raiz.iter_nodos(nivel_maximo=1)]
        self.assertEqual(len(nodos_n1), 1)
        nodos_todos = [n for _, n in self.raiz.iter_nodos()]
        self.assertEqual(len(nodos_todos), 3)

    def test_unidad_invalida(self):
        """RNF-03 video 6: la unidad se valida contra lista."""
        with self.assertRaises(ValueError):
            Concepto("C9", "Mal", "MTS2", 1)


if __name__ == "__main__":
    unittest.main()
