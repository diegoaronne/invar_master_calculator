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
