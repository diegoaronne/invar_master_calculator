"""Pruebas de la capa web (webapp/) contra los criterios de aceptación
del brief:

- El wizard permite generar un presupuesto nuevo de principio a fin.
- La vista cliente nunca expone indirectos/financiamiento/utilidad ni
  columnas no imprimibles.
- Dos sesiones demo simultáneas no interfieren entre sí.
- El botón de reset demo funciona.

Requiere `httpx` (cliente de pruebas de FastAPI); si no está instalado,
la suite se omite sin fallar para no bloquear las pruebas del motor.
"""
import unittest
import warnings

try:
    from fastapi.testclient import TestClient
    from webapp.main import app, DEMO_PASSWORD
    _WEBAPP_DISPONIBLE = True
except ImportError:  # pragma: no cover - entorno sin dependencias web
    _WEBAPP_DISPONIBLE = False

warnings.filterwarnings("ignore")


def _cliente_logueado():
    cliente = TestClient(app)
    cliente.post("/login", data={"password": DEMO_PASSWORD},
                 follow_redirects=False)
    return cliente


@unittest.skipUnless(_WEBAPP_DISPONIBLE,
                     "fastapi/httpx no instalados; suite web omitida")
class TestLoginYSesiones(unittest.TestCase):
    def test_login_incorrecto_no_crea_sesion(self):
        cliente = TestClient(app)
        r = cliente.post("/login", data={"password": "incorrecta"},
                         follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("error", r.headers["location"])
        r = cliente.get("/reportes/interno")
        self.assertEqual(r.status_code, 440)

    def test_login_correcto_entrega_demo(self):
        cliente = _cliente_logueado()
        r = cliente.get("/dashboard")
        self.assertEqual(r.status_code, 200)
        self.assertIn("DEMO", r.text)

    def test_sesiones_simultaneas_aisladas(self):
        """Criterio: dos pestañas/navegadores no se pisan datos."""
        a, b = _cliente_logueado(), _cliente_logueado()
        a.post("/proyecto/nuevo", follow_redirects=False)
        a.post("/wizard/1", data={"nombre": "Proyecto solo de A",
                                  "iva_pct": "16"},
               follow_redirects=False)
        self.assertIn("Proyecto solo de A", a.get("/dashboard").text)
        texto_b = b.get("/dashboard").text
        self.assertNotIn("Proyecto solo de A", texto_b)
        self.assertIn("DEMO", texto_b)

    def test_reset_demo(self):
        cliente = _cliente_logueado()
        cliente.post("/proyecto/nuevo", follow_redirects=False)
        cliente.post("/wizard/1", data={"nombre": "Temporal",
                                        "iva_pct": "16"},
                     follow_redirects=False)
        cliente.post("/reset-demo", follow_redirects=False)
        self.assertIn("DEMO", cliente.get("/dashboard").text)


@unittest.skipUnless(_WEBAPP_DISPONIBLE,
                     "fastapi/httpx no instalados; suite web omitida")
class TestVistaCliente(unittest.TestCase):
    def setUp(self):
        self.cliente = _cliente_logueado()

    def test_cliente_no_ve_tablas_internas(self):
        """Criterio: la vista cliente nunca expone indirectos,
        financiamiento, utilidad ni FSR."""
        texto = self.cliente.get("/reportes/cliente").text
        for prohibido in ("Pie de precios", "Financiamiento",
                          "Factor de Salario Real", "Explosión de insumos",
                          "COSTO DIRECTO"):
            self.assertNotIn(prohibido, texto)
        self.assertIn("TOTAL CON IVA", texto)

    def test_interno_si_ve_todo(self):
        texto = self.cliente.get("/reportes/interno").text
        for esperado in ("Pie de precios", "Financiamiento",
                         "Factor de Salario Real", "Explosión de insumos"):
            self.assertIn(esperado, texto)

    def test_apu_cliente_sin_margenes(self):
        interno = self.cliente.get("/reportes/interno/apu/C-LOSA").text
        self.assertIn("Utilidad", interno)
        publico = self.cliente.get("/reportes/cliente/apu/C-LOSA").text
        self.assertIn("PRECIO UNITARIO DE VENTA", publico)
        self.assertNotIn("Utilidad", publico)
        self.assertNotIn("COSTO DIRECTO", publico)

    def test_columna_no_imprimible_oculta_en_html(self):
        """RF-04 video 34 aplicado a la capa web."""
        from invar_calculator.reportes import Columna, Tabla
        from webapp.render_html import tabla_a_html
        tabla = Tabla("Prueba", ["Clave", Columna("Interno",
                                                  imprimible=False)])
        tabla.agregar_fila("C1", "secreto")
        self.assertNotIn("secreto", tabla_a_html(tabla))
        self.assertIn("secreto",
                      tabla_a_html(tabla, solo_imprimibles=False))

    def test_csv_descargable(self):
        r = self.cliente.get("/reportes/interno/csv/0")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers["content-type"])
        self.assertIn("TOTAL CON IVA", r.text)


@unittest.skipUnless(_WEBAPP_DISPONIBLE,
                     "fastapi/httpx no instalados; suite web omitida")
class TestWizardCompleto(unittest.TestCase):
    """Criterio: se puede completar el wizard de principio a fin y
    generar un presupuesto nuevo desde cero, sin editar código."""

    def _post_ok(self, cliente, url, data=None):
        r = cliente.post(url, data=data or {}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, url)
        self.assertNotIn("error", r.headers.get("location", ""),
                         f"{url}: {r.headers.get('location')}")

    def test_wizard_de_cero_a_presupuesto(self):
        c = _cliente_logueado()
        self._post_ok(c, "/proyecto/nuevo")
        self._post_ok(c, "/wizard/1", {
            "nombre": "Obra wizard", "cliente": "Cliente",
            "fecha_inicio": "2026-08-03", "fecha_fin": "2026-10-31",
            "iva_pct": "16"})
        self._post_ok(c, "/wizard/2/material", {
            "clave": "CEM", "descripcion": "Cemento", "unidad": "ton",
            "costo": "2850"})
        self._post_ok(c, "/wizard/2/mano-obra", {
            "clave": "PEON", "descripcion": "Peón", "salario_base": "310",
            "usa_fsr": "on"})
        self._post_ok(c, "/wizard/2/compuesto", {
            "tipo": "cuadrilla", "clave": "CUAD", "descripcion": "Cuadrilla"})
        self._post_ok(c, "/wizard/2/componente", {
            "padre": "CUAD", "recurso": "PEON", "cantidad": "2"})
        self._post_ok(c, "/wizard/3/matriz", {
            "clave": "M1", "descripcion": "Firme", "unidad": "m2"})
        self._post_ok(c, "/wizard/3/insumo", {
            "matriz": "M1", "recurso": "CEM", "cantidad": "0.02"})
        self._post_ok(c, "/wizard/3/insumo", {
            "matriz": "M1", "recurso": "CUAD", "cantidad": "0.1"})
        self._post_ok(c, "/wizard/4/agrupador", {
            "padre": "", "clave": "01", "descripcion": "Preliminares"})
        self._post_ok(c, "/wizard/4/concepto", {
            "agrupador": "01", "clave": "C-01", "descripcion": "Firme",
            "unidad": "m2", "cantidad": "0", "matriz": "M1"})
        self._post_ok(c, "/wizard/4/generador", {
            "concepto": "C-01", "referencia": "Tramo A", "largo": "120",
            "ancho": "7.5", "alto": "", "piezas": "1",
            "cantidad_directa": ""})
        self._post_ok(c, "/wizard/5/calendario", {
            "fecha": "2026-09-16", "estado_dia": "NO_TRABAJABLE",
            "horas": ""})
        self._post_ok(c, "/wizard/5/actividad", {
            "concepto": "C-01", "inicio": "2026-08-03", "duracion": "20",
            "porcentaje": "100"})
        self._post_ok(c, "/wizard/5/sincronizar")
        self._post_ok(c, "/wizard/6/utilidad", {
            "isr_pct": "30", "ptu_pct": "10", "utilidad_neta_pct": "6"})
        self._post_ok(c, "/wizard/6/financiamiento", {
            "tasa_activa": "14.5", "tasa_pasiva": "8",
            "desfase_cobro": "2", "anticipo_pct": "30"})
        self._post_ok(c, "/wizard/6/aplicar")

        texto = c.get("/reportes/interno").text
        self.assertIn("Obra wizard", texto)
        self.assertIn("TOTAL CON IVA", texto)
        self.assertIn("Utilidad", texto)
        # La cantidad viene de los generadores: 120 × 7.5 = 900.
        self.assertIn("900", texto)

    def test_error_del_motor_llega_como_flash(self):
        c = _cliente_logueado()
        r = c.post("/wizard/3/insumo",
                   data={"matriz": "NO-EXISTE", "recurso": "CEM-01",
                         "cantidad": "1"},
                   follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("error", r.headers["location"])


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_WEBAPP_DISPONIBLE,
                     "fastapi/httpx no instalados; suite web omitida")
class TestHojaPresupuesto(unittest.TestCase):
    """Vista de trabajo estilo OPUS: tree-grid, edición en celda y Gantt."""

    def setUp(self):
        self.cliente = _cliente_logueado()

    def test_hoja_y_api_devuelven_presupuesto(self):
        r = self.cliente.get("/hoja")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Hoja de presupuesto", r.text)

        datos = self.cliente.get("/api/hoja").json()
        self.assertTrue(datos["ok"])
        ids = [f["id"] for f in datos["hoja"]["filas"]]
        self.assertIn("a:02", ids)
        self.assertIn("c:C-LOSA", ids)
        fila = next(f for f in datos["hoja"]["filas"] if f["id"] == "c:C-LOSA")
        self.assertEqual(fila["padre"], "a:02")
        self.assertEqual(fila["matriz"], "MAT-LOSA")
        self.assertIn("total_con_iva", datos["hoja"]["resumen"])

    def test_editar_cantidad_recalcula_totales(self):
        antes = self.cliente.get("/api/hoja").json()["hoja"]
        r = self.cliente.patch("/api/concepto/C-LOSA",
                               json={"cantidad": "3224"})
        despues = r.json()
        self.assertTrue(despues["ok"])
        self.assertNotEqual(antes["resumen"]["precio_venta"],
                            despues["hoja"]["resumen"]["precio_venta"])
        fila = next(f for f in despues["hoja"]["filas"]
                    if f["id"] == "c:C-LOSA")
        self.assertEqual(fila["cantidad"], "3224")

    def test_cantidad_con_generador_se_rechaza(self):
        r = self.cliente.patch("/api/concepto/C-BASE",
                               json={"cantidad": "99"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("generadores", r.json()["error"])

    def test_cantidad_invalida_se_rechaza_y_no_rompe(self):
        r = self.cliente.patch("/api/concepto/C-LOSA",
                               json={"cantidad": "abc"})
        self.assertEqual(r.status_code, 400)
        r = self.cliente.get("/api/hoja")
        self.assertTrue(r.json()["ok"])

    def test_editar_descripcion_agrupador(self):
        r = self.cliente.patch("/api/agrupador",
                               json={"ruta": "02",
                                     "descripcion": "Pavimento rígido"})
        self.assertTrue(r.json()["ok"])
        fila = next(f for f in r.json()["hoja"]["filas"]
                    if f["id"] == "a:02")
        self.assertEqual(fila["descripcion"], "Pavimento rígido")

    def test_alta_rapida_de_capitulo_y_concepto(self):
        r = self.cliente.post("/hoja/capitulo",
                              data={"padre": "", "clave": "03",
                                    "descripcion": "Señalización"},
                              follow_redirects=False)
        self.assertIn("ok=", r.headers["location"])
        r = self.cliente.post("/hoja/concepto",
                              data={"padre": "03", "clave": "C-SEN",
                                    "descripcion": "Pintura de raya",
                                    "unidad": "ml", "cantidad": "500",
                                    "matriz": "MAT-BASE"},
                              follow_redirects=False)
        self.assertIn("ok=", r.headers["location"])
        ids = [f["id"] for f in
               self.cliente.get("/api/hoja").json()["hoja"]["filas"]]
        self.assertIn("a:03", ids)
        self.assertIn("c:C-SEN", ids)

    def test_gantt_expone_barras_y_ruta_critica(self):
        gantt = self.cliente.get("/api/gantt").json()["gantt"]
        self.assertIsNotNone(gantt)
        self.assertIn("c:C-LOSA", gantt["barras"])
        self.assertTrue(gantt["barras"]["c:C-LOSA"][0]["critica"])
        self.assertIn("a:02", gantt["barras"])  # barra resumen del capítulo
        self.assertTrue(gantt["meses"])

    def test_gantt_sin_programa_devuelve_null(self):
        self.cliente.post("/proyecto/nuevo", follow_redirects=False)
        r = self.cliente.get("/api/gantt")
        self.assertIsNone(r.json()["gantt"])


@unittest.skipUnless(_WEBAPP_DISPONIBLE,
                     "fastapi/httpx no instalados; suite web omitida")
class TestFichaCosteo(unittest.TestCase):
    """Ficha de matriz: insumos editables, filtros por tipo y pie."""

    def setUp(self):
        self.cliente = _cliente_logueado()

    def test_ficha_carga_con_subtotales_y_pie(self):
        r = self.cliente.get("/matriz/MAT-LOSA?concepto=C-LOSA")
        self.assertEqual(r.status_code, 200)
        datos = self.cliente.get(
            "/api/matriz/MAT-LOSA?concepto=C-LOSA").json()["ficha"]
        tipos = [s["tipo"] for s in datos["subtotales"]]
        self.assertEqual(tipos[0], "Todos")
        self.assertIn("Mano de obra", tipos)
        self.assertEqual(datos["concepto"]["clave"], "C-LOSA")
        self.assertIn("C-LOSA", datos["conceptos_vinculados"])
        ids_pie = [r_["id"] for r_ in datos["pie"]["renglones"]]
        self.assertEqual(ids_pie[:2], ["IND_OF", "IND_CAMPO"])

    def test_editar_cantidad_de_insumo_recalcula(self):
        antes = self.cliente.get("/api/matriz/MAT-LOSA").json()["ficha"]
        r = self.cliente.patch("/api/matriz/MAT-LOSA/insumo/MALLA-01",
                               json={"cantidad": "2.10"})
        despues = r.json()["ficha"]
        self.assertNotEqual(antes["costo_directo_fmt"],
                            despues["costo_directo_fmt"])
        insumo = next(i for i in despues["insumos"]
                      if i["clave"] == "MALLA-01")
        self.assertEqual(insumo["cantidad"], "2.10")

    def test_cantidad_acepta_formula(self):
        r = self.cliente.patch("/api/matriz/MAT-LOSA/insumo/MALLA-01",
                               json={"cantidad": "1/10"})
        self.assertTrue(r.json()["ok"])

    def test_agregar_y_quitar_insumo(self):
        r = self.cliente.post("/api/matriz/MAT-LOSA/insumo",
                              json={"recurso": "ARE-01", "cantidad": "0.5"})
        claves = [i["clave"] for i in r.json()["ficha"]["insumos"]]
        self.assertIn("ARE-01", claves)
        # Duplicado se rechaza.
        r = self.cliente.post("/api/matriz/MAT-LOSA/insumo",
                              json={"recurso": "ARE-01", "cantidad": "1"})
        self.assertEqual(r.status_code, 400)
        r = self.cliente.delete("/api/matriz/MAT-LOSA/insumo/ARE-01")
        claves = [i["clave"] for i in r.json()["ficha"]["insumos"]]
        self.assertNotIn("ARE-01", claves)

    def test_editar_costo_de_material(self):
        r = self.cliente.patch("/api/recurso/MALLA-01?matriz=MAT-LOSA",
                               json={"costo": "96"})
        insumo = next(i for i in r.json()["ficha"]["insumos"]
                      if i["clave"] == "MALLA-01")
        self.assertEqual(insumo["costo"], "96")
        # Un compuesto no admite costo directo.
        r = self.cliente.patch("/api/recurso/CUAD-01?matriz=MAT-LOSA",
                               json={"costo": "100"})
        self.assertEqual(r.status_code, 400)

    def test_editar_pie_cambia_precio_venta(self):
        antes = self.cliente.get("/api/matriz/MAT-LOSA").json()["ficha"]
        r = self.cliente.patch("/api/pie/UTIL?matriz=MAT-LOSA",
                               json={"porcentaje": "25"})
        despues = r.json()["ficha"]
        self.assertNotEqual(antes["precio_venta_fmt"],
                            despues["precio_venta_fmt"])
        r = self.cliente.patch("/api/pie/UTIL?matriz=MAT-LOSA",
                               json={"base": "Directo"})
        self.assertTrue(r.json()["ok"])
        util = next(r_ for r_ in r.json()["ficha"]["pie"]["renglones"]
                    if r_["id"] == "UTIL")
        self.assertEqual(util["base"], "Directo")


@unittest.skipUnless(_WEBAPP_DISPONIBLE,
                     "fastapi/httpx no instalados; suite web omitida")
class TestConfiguracionPie(unittest.TestCase):
    def setUp(self):
        self.cliente = _cliente_logueado()

    def test_pagina_y_alta_baja_de_cargos(self):
        r = self.cliente.get("/pie")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Indirectos de oficina central", r.text)

        r = self.cliente.post("/pie/cargo",
                              data={"identificador": "POT",
                                    "nombre": "Otro porcentaje",
                                    "porcentaje": "1.5",
                                    "base": "Directo"},
                              follow_redirects=False)
        self.assertIn("ok=", r.headers["location"])
        self.assertIn("POT", self.cliente.get("/pie").text)

        r = self.cliente.post("/pie/cargo/POT",
                              data={"nombre": "Porcentaje municipal",
                                    "porcentaje": "2", "base": "Acumulable"},
                              follow_redirects=False)
        self.assertIn("ok=", r.headers["location"])
        self.assertIn("Porcentaje municipal", self.cliente.get("/pie").text)

        r = self.cliente.post("/pie/cargo/POT/eliminar",
                              follow_redirects=False)
        self.assertIn("ok=", r.headers["location"])
        self.assertNotIn("Porcentaje municipal", self.cliente.get("/pie").text)

    def test_cambio_de_modo(self):
        r = self.cliente.post("/pie/modo", data={"modo": "Avanzado"},
                              follow_redirects=False)
        self.assertIn("ok=", r.headers["location"])
        self.assertIn("Fórmula", self.cliente.get("/pie").text)
