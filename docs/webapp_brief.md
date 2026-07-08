# INVAR Master Calculator — Web App: Brief técnico para Claude Code

## Contexto
`invar_calculator` es un motor de presupuestos de obra en Python puro (2,660 líneas:
FSR, catálogo de recursos, matrices, WBS/conceptos, calendario, indirectos,
financiamiento, utilidad, reportes). Hoy solo se usa vía `demo.py`, que imprime
reportes en texto plano por consola. **No hay interfaz web.**

Este brief define cómo envolver ese motor en una aplicación web para uso interno
(Diego/Marcelo) y para mostrar propuestas a clientes/socios, sin tocar la lógica
de cálculo ya probada (`tests/` debe seguir pasando sin modificaciones).

## Objetivo de esta fase
1. Wizard web paso a paso para capturar un proyecto nuevo (reemplaza editar `demo.py` a mano).
2. Dos vistas de reporte: **interna** (todo, incluida utilidad/indirectos/financiamiento)
   y **cliente** (solo presupuesto final y APU sin desglose de márgenes).
3. Modo demo con sesión aislada por usuario (sin cuentas reales todavía — eso es la
   fase multitenant futura, NO construir ahora).

## Decisión de arquitectura (ya tomada, no relitigar)
- **Backend:** FastAPI (no Flask) — Pydantic calza con los dataclasses del motor,
  y da validación automática de formularios/JSON.
- **Frontend fase 1:** Jinja2 templates + HTML/CSS simple. Nada de React todavía —
  se puede migrar después si se necesita más interactividad (edición de tablas en vivo).
- **Persistencia fase 1:** en memoria, por sesión (ver `webapp/session_store.py`).
  Nada de SQLite/Postgres todavía. Cuando llegue multitenant, este store se
  reemplaza por uno respaldado en DB, pero la interfaz (`get`, `put`, `reset`)
  debe mantenerse igual para no reescribir los routers.
- **No modificar `invar_calculator/reportes.py`.** La clase `Tabla` ya expone
  `.columnas` (con flag `imprimible`, pensado para RF-04/RNF-02) y `.filas` como
  atributos públicos. La conversión a HTML vive en `webapp/render_html.py`,
  una capa nueva que consume esos datos sin tocar el motor.
- **Vista cliente vs interna:** se controla filtrando qué `Tabla`s se muestran
  (ej. ocultar "Pie de precios unitarios" y "Financiamiento" en modo cliente)
  y usando `columna.imprimible=False` para ocultar columnas sensibles dentro
  de tablas que sí se muestran (ej. costo unitario interno en un reporte de
  conceptos que el cliente sí debe ver).

## Ya entregado en este starter (funcional, probado)
```
webapp/
  main.py            # App FastAPI, login demo, rutas base
  session_store.py   # Almacén de proyectos en memoria por sesión (UUID en cookie)
  demo_seed.py        # Construye el proyecto demo (misma lógica que demo.py)
  render_html.py       # Convierte Tabla -> HTML, con soporte de vista interna/cliente
  routers/
    reportes.py         # Rutas para ver reportes (interno y cliente) del proyecto en sesión
  templates/
    base.html
    login.html
    dashboard.html
    reporte.html
  static/styles.css
```
Correr con: `uvicorn webapp.main:app --reload` desde la raíz del repo
(con `invar_calculator/` como paquete hermano de `webapp/`).

Login demo: contraseña en `webapp/main.py` → variable `DEMO_PASSWORD` (cambiarla
por variable de entorno antes de compartir el link fuera del equipo).

## Pendiente — próximos módulos a construir (en orden sugerido)

### 1. Wizard de captura — Paso 1: Datos generales del proyecto
- Formulario: nombre del proyecto, cliente, autor, descripción de obra,
  ubicación, fecha inicio/fin, responsables (lista dinámica de inputs).
- Mapea a `ic.Proyecto(nombre, datos=ic.DatosGenerales(...))`.
- Al enviar, crea un nuevo proyecto en la sesión (reemplaza el demo o inicia
  uno nuevo — decidir con Diego si el wizard parte siempre de cero o permite
  clonar el demo como plantilla).

### 2. Wizard — Paso 2: Catálogo de recursos
- Tabla editable (agregar fila) para materiales: clave, descripción, unidad, costo, familia.
- Sección aparte para mano de obra (salario_base) y para recursos compuestos
  (cuadrillas: agregar componentes con proporción, incluye fracciones tipo "1/10" —
  **cuidado**: el motor acepta strings de fracción, no solo Decimal, ver `Recurso.agregar_componente`).
- Sección para auxiliares (recetas reutilizables, ej. concreto) y equipo con
  costo horario (`DatosCostoHorario` — formulario más largo, 15 campos).

### 3. Wizard — Paso 3: Matrices de precios unitarios
- Por cada matriz: clave, descripción, unidad, lista de insumos con cantidad
  (selector de recurso ya cargado en catálogo + cantidad).

### 4. Wizard — Paso 4: Estructura WBS y conceptos
- Árbol de agrupadores (ej. "01 Preliminares", "02 Pavimento").
- Conceptos dentro de cada agrupador: clave, descripción, unidad, matriz asociada,
  y cantidad (fija o vía `NumerosGeneradores` — sub-formulario de líneas
  largo/ancho/alto con descripción, para obras con medición por tramos).

### 5. Wizard — Paso 5: Calendario y programa de obra
- Marcar días no laborables/personalizados en un calendario visual (considerar
  un date-picker con multi-selección, no un formulario de texto).
- Programar actividades: concepto, fecha inicio, duración laborable, predecesoras
  (para calcular ruta crítica vía `programa.actividades_criticas()`).

### 6. Wizard — Paso 6: Indirectos, financiamiento y utilidad
- Formulario de `CalculoIndirectos` (método oficina central, personal indirecto,
  gastos indirectos).
- Formulario de `CalculoFinanciamiento` (tasas, desfase de cobro, anticipo).
- Formulario de `CalculoUtilidad` (ISR, PTU, utilidad neta).
- Cargos adicionales (`proyecto.pie.asignar_porcentaje`).

### 7. Reportes — completar vista cliente
- Ya está el esqueleto en `render_html.py`. Falta decidir con Diego, tabla por
  tabla, qué se oculta en modo cliente. Sugerencia inicial (confirmar):
  - **Cliente ve:** Presupuesto jerárquico (sin columna de precio unitario
    interno si se decide ocultarla), Total con IVA.
  - **Cliente NO ve:** Pie de precios unitarios, reporte de financiamiento,
    desglose de indirectos, FSR, explosión de insumos por costo.
  - **Cliente sí podría ver (opcional, a confirmar):** programa de obra /
    cronograma, como valor agregado de transparencia.

### 8. Exportación
- Botón "Exportar PDF" en vista cliente (usar la skill de `pdf` del entorno,
  o `weasyprint`/`playwright` si se corre server-side).
- El motor ya exporta CSV (ver `reportes.py`) — exponer como endpoint de descarga
  directa, útil para Excel.

## Routing de modelos sugerido (para no quemar cupo de Fable 5 innecesariamente)
- **Fable 5:** diseño de la separación vista interna/cliente (paso 7), diseño
  del store de sesión pensando en la futura migración a multitenant (ya resuelto
  en este starter, pero revisar si se extiende), y cualquier decisión de
  arquitectura no trivial que surja.
- **Sonnet 5 / Opus 4.8:** los formularios CRUD de los pasos 1-6 (patrón repetitivo,
  no requiere razonamiento profundo), templates HTML, tests.

## 9. Deploy (Render o Railway)
Objetivo: tener una URL pública para que clientes/socios prueben la vista
cliente sin que Diego les pase su laptop. No es para producción con carga
real todavía — es para la fase de "uso interno + mostrar a clientes/socios".

### Preparativos en el repo
- [ ] Agregar `requirements.txt` en la raíz (fusionar `requirements_webapp.txt`
  de este starter con las dependencias que ya use `invar_calculator`, si tiene).
- [ ] Agregar `Procfile` (Render lo soporta, aunque no es obligatorio) o
  configurar el "Start Command" directo en el panel: 
  `uvicorn webapp.main:app --host 0.0.0.0 --port $PORT`
- [ ] Mover `DEMO_PASSWORD` a variable de entorno obligatoria (`INVAR_DEMO_PASSWORD`)
  — no dejar el default `"invar2026"` en el código para el deploy público.
- [ ] Confirmar que `session_store.py` sigue siendo válido en un solo proceso
  (Render free tier corre 1 instancia — sin problema). Si más adelante se usa
  un plan con múltiples instancias/autoscaling, el store en memoria por
  proceso deja de servir y hay que pasar a Redis o DB antes de escalar.

### Render (opción recomendada — más simple para este caso)
1. Crear cuenta en render.com, conectar el repo de GitHub
  (`diegoaronne/invar_master_calculator`).
2. "New Web Service" → seleccionar el repo y la rama (`claude/development-requirements-li8dp0`
  o la que se use para esto).
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn webapp.main:app --host 0.0.0.0 --port $PORT`
5. Agregar variable de entorno `INVAR_DEMO_PASSWORD` en el panel de Render
  (no en el código).
6. Plan gratuito: la instancia se "duerme" tras ~15 min sin tráfico y tarda
  unos segundos en despertar en la siguiente visita — aceptable para demo con
  clientes avisados, pero considerar el plan pago (~$7/mes) si se va a mandar
  el link sin previo aviso a alguien que decide en el momento (ej. mitad de
  una llamada de venta).

### Railway (alternativa, similar simplicidad)
1. railway.app → conectar repo de GitHub.
2. Railway detecta Python automáticamente; si no, definir el start command
  igual que arriba.
3. Variables de entorno en la pestaña "Variables" del proyecto.
4. Railway no duerme instancias en el plan gratuito por tiempo, pero el
  crédito gratuito es limitado por mes — vigilar consumo si el link circula
  bastante.

### Después del deploy
- [ ] Probar el flujo completo (login demo → dos pestañas distintas → verificar
  que no se pisan datos) contra la URL pública, no solo en local.
- [ ] Decidir con Diego si la landing de Notion (ver conversación aparte)
  enlaza directo a esta URL, o si primero pasa por un formulario de captura
  de interesados antes de dar el acceso a la demo.

## Criterios de aceptación de esta fase
- [ ] `pytest tests/` sigue pasando sin cambios (motor intacto).
- [ ] Se puede completar el wizard de principio a fin y generar un presupuesto
  nuevo desde cero, sin editar código.
- [ ] La vista cliente nunca expone indirectos/financiamiento/utilidad ni
  columnas marcadas como no imprimibles.
- [ ] Dos sesiones demo simultáneas (dos pestañas/navegadores distintos) no
  interfieren entre sí.
- [ ] Botón de reset demo funcional.
