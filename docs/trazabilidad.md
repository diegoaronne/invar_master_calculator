# Matriz de trazabilidad — Requerimientos → Implementación

Origen: tres documentos de especificación (`reqs_sopu`) con requerimientos
funcionales (RF) y no funcionales (RNF) derivados de los videos 1–35 del
análisis de OPUS Planet.

Estados: ✅ implementado en el motor · 🔶 parcial (la lógica de dominio
existe; la experiencia interactiva corresponde a una capa de UI futura) ·
⬜ fase posterior (UI/infraestructura, fuera del alcance del motor de
cálculo).

## Documento 1 (videos 1–7): proyectos, WBS y conceptos

| Req. | Descripción | Estado | Implementación |
|---|---|---|---|
| V1 RF-01 | Nombre de proyecto ≤ 128 caracteres | ✅ | `proyecto.Proyecto` (validación) |
| V1 RF-02 | Parámetros generales (Datos/Configuración) | ✅ | `proyecto.DatosGenerales` |
| V1 RF-03 | Fechas de proyecto y sincronización | ✅ | `programa.ProgramaObra.sincronizar_fechas` |
| V1 RF-04 | Catálogos de responsables/registros | ✅ | `DatosGenerales.responsables/registros` |
| V1 RF-05 | Decimales, IVA, monedas | ✅ | `precision.ConfiguracionPrecision`, `Proyecto.iva_pct`, `moneda` |
| V1 RNF-01 | Persistencia en SQL Server | ⬜ | Fase de infraestructura |
| V1 RNF-03 | Control de calendario en fechas | 🔶 | Tipos `datetime.date` en todo el dominio |
| V2 RF-01 | Sobrecostos (financiamiento/utilidad, ISR, PTU, anticipos) | ✅ | `financiamiento`, `utilidad` |
| V2 RF-02 | Multimoneda (nombre, símbolo, fracción, tipo de cambio) | ✅ | `moneda.SistemaMonedas` |
| V2 RF-03 | Motor FSR parametrizable | ✅ | `fsr.HojaFSR` |
| V2 RF-04 | Parámetros de costo horario (fórmulas o manual, HP→kW 0.746) | ✅ | `costo_horario` (`FACTOR_HP_KW`, `calculo_manual`) |
| V2 RF-05 | 8 tipos de recursos con alias modificables | ✅ | `modelos.TipoRecurso`, `Catalogo.alias_tipos` |
| V3 RF-01..06 | Historial, conexión remota, MDI, drag&drop entre proyectos | 🔶 | Dominio: `Agrupador.clonar_en`, `Catalogo.reemplazar_referencias`; UI ⬜ |
| V4 RF-01..06 | Vistas, columnas, WBS, matrices vinculadas y reutilizables | ✅ | `modelos.Matriz` (concepto/matriz desacoplados), `reportes.Columna` |
| V5 RF-01..07 | Agrupadores: niveles ilimitados, claves, clonación, indentar, borrado en cascada | ✅ | `modelos.Agrupador` |
| V6 RF-01..04 | Conceptos: captura, atributos, unidad validada, portapapeles | ✅/🔶 | `modelos.Concepto`, `UNIDADES_PREDEFINIDAS`; portapapeles = capa UI |
| V7 RF-01..05 | Búsqueda en catálogos, importación con APU, conflictos, comodines | ✅ | `Catalogo.buscar` (wildcards), `reemplazar_referencias`, `Matriz.copiar_desglose_desde` |

## Documento 2 (videos 8–20): recursos y precios unitarios

| Req. | Descripción | Estado | Implementación |
|---|---|---|---|
| V8 RF-02/03/04 | Copia de ramas WBS entre proyectos con resolución de conflictos | ✅ | `Agrupador.clonar_en`, `Catalogo.reemplazar_referencias`, `Agrupador.subir_nivel/bajar_nivel` |
| V9 RF-01..05 | Vista plana, filtros con comodines, query builder, ir al origen | 🔶 | `Agrupador.iter_conceptos` (vista plana), `Catalogo.buscar`; query builder visual ⬜ |
| V10 RF-01..04 | Números generadores (referencia, dimensiones, factor, híbrido) | ✅ | `generadores.NumerosGeneradores` |
| V10 RNF-02 | Cantidad del presupuesto actualizada al instante | ✅ | `Concepto.cantidad_efectiva` |
| V11 RF-01..04 | Migración desde OPUS 2010/2009 (wizard, ETL) | ⬜ | Fase de infraestructura |
| V12 RF-01..04 | Matrices: acceso, filtros por tipo, desglose recursivo, resumen | ✅ | `Matriz.insumos_por_tipo`, `Recurso.iter_recursivo`, `Matriz.resumen_por_tipo` |
| V12 RNF-03 | Matrices anidadas sin referencias circulares | ✅ | `modelos._validar_no_circular` |
| V13 RF-01..05 | Materiales: simple/compuesto, metadatos, fórmulas de costo, indivisible | ✅ | `Recurso` (familia, vigencia, `formula_costo`, `indivisible`) |
| V13 RNF-02 | Clave existente vincula en lugar de duplicar | ✅ | `Catalogo.registrar` |
| V14 RF-01..04 | Mano de obra: cuadrillas compuestas, FSR automático, fórmulas `2/20` | ✅ | `Recurso.salario_base/usa_fsr/fsr_manual`, `Insumo.cantidad` con fórmula |
| V15 RF-01..05 | Costo horario: 3 cargos, deducción de llantas, vida económica, tasas, mantenimiento | ✅ | `costo_horario.DatosCostoHorario` |
| V16 RF-01..04 | Consumos automáticos/manuales, lubricación, operación, llantas | ✅ | `cargos_consumo`, `cargos_operacion`, coeficientes modificables |
| V17 RF-01..04 | Herramienta `%MO` reactiva y equipo de seguridad | ✅ | `Recurso.es_porcentaje_mo` (costo sobre MO de la matriz) |
| V18 RF-01..04 | Auxiliares: recursividad, "dónde participa", validación de ciclos | ✅ | `Catalogo.donde_participa`, `ErrorReferenciaCircular` |
| V19 RF-01..05 | Explorador de paramétricos (plantillas geométricas) | ⬜ | Fase posterior |
| V20 RF-01..05 | Catálogos por tipo, homologación de claves, conversión de tipo | ✅ | `Catalogo.por_tipo/homologar/cambiar_tipo` |

## Documento 3 (videos 21–35): FSR, programación, sobrecostos y reportes

| Req. | Descripción | Estado | Implementación |
|---|---|---|---|
| V21 RF-01..05 | FSR: variables de entorno, calendario, prestaciones, cuotas, reportes | ✅ | `fsr.HojaFSR`, `reporte_factor_ps`, `reporte_fsr` |
| V21 RNF-02 | Prevención de duplicidad de ISN | ✅ | `HojaFSR.incluir_isn` + `Proyecto.validar` |
| V21 RNF-03 | Precisión configurable (5 decimales) | ✅ | `ConfiguracionPrecision.fsr` |
| V22/V28 RF-01..05 | Explosión de insumos: filtros, desglose de equipo, escalas, montos/cantidades | ✅ | `explosion.ExplosionInsumos`, `ProgramaSuministros` |
| V22 RNF-01 | Interoperabilidad (copiar a Excel) | ✅ | `reportes.Tabla.a_csv` |
| V23 RF-01..05 | Vistas del programa, ruta crítica, calendario | ✅ | `programa.ruta_critica`, `programa_cantidades/montos`; zoom/estilos = UI ⬜ |
| V24 RF-01..03 | Calendario: 4 estados de día, jornadas puntuales | ✅ | `calendario.CalendarioTrabajo` |
| V24 RNF-01 | El calendario restringe el Gantt | ✅ | `CalendarioTrabajo.sumar_laborables` usado por `Segmento.fechas` |
| V25 RF-01..04 | Copia de matrices entre proyectos, conflictos de recursos | ✅ | `Matriz.copiar_desglose_desde`, `Catalogo.reemplazar_referencias` |
| V26 RF-01..04 | Auditoría de fechas, proyecto vs programa, fraccionamiento | ✅ | `ProgramaObra.auditoria/sincronizar_fechas`, `Segmento.porcentaje` |
| V26 RNF-01 | Alertas de desfase temporal | ✅ | `ProgramaObra.alertas` |
| V28 RF-01..04 | Pie de precios: estándar/avanzado, directo/acumulable, recálculo | ✅ | `pie_precios.PiePrecios`, `Proyecto.recalcular` |
| V29 RF-01..05 | Indirectos: central/campo, % vs anualizado, plantillas, transferir | ✅ | `indirectos.CalculoIndirectos` |
| V30 RF-01..03 | Programa de personal en indirectos | 🔶 | `CalculoIndirectos.desglose_personal` + distribución de `programa`; vista Gantt dedicada ⬜ |
| V31 RF-01..05 | Diseñador WYSIWYG de encabezados/pies | ⬜ | Capa de UI futura |
| V32 RF-01..05 | Financiamiento: formatos H/V, desfase, tasas, anticipos parciales, inyección | ✅ | `financiamiento.CalculoFinanciamiento`, `reportes.reporte_financiamiento` |
| V32 RNF-01 | Precondición programa + explosión | ✅ | `financiamiento.ErrorPrecondicion` |
| V33 RF-01..05 | Utilidad: ISR/PTU, neta→bruta, hoja de cálculo, transferencia | ✅ | `utilidad.CalculoUtilidad` |
| V34 RF-01..05 | Reportes: alcance, columnas imprimibles, exportación | ✅/🔶 | `reportes.Tabla` (+`Columna.imprimible`), CSV; configuración de página/impresora ⬜ |
| V35 RF-01..03 | Exportación PDF/XLSX con seguridad y metadatos | 🔶 | CSV nativo; PDF/XLSX requieren dependencias externas (fase posterior) |

## Requerimientos transversales

| Tema | Estado | Implementación |
|---|---|---|
| Aritmética exacta (sin errores de punto flotante) | ✅ | `decimal.Decimal` en todo el motor (`precision.D`) |
| Fórmulas seguras en cantidades y costos | ✅ | `formulas.evaluar_formula` (AST restringido, sin `eval`) |
| Integridad referencial (borrado en cascada, claves) | ✅ | `Agrupador.eliminar`, `Catalogo` |
| Recalculo consistente tras cambiar sobrecostos | ✅ | `Proyecto.recalcular` (RF-04 video 28) |
| Rendimiento (explosiones "en segundos") | ✅ | Suite completa (103 pruebas + demo integral) corre en <1 s |
