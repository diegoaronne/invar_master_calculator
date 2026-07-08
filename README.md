# INVAR Master Calculator

Motor de cálculo para **presupuestos de obra y precios unitarios**,
desarrollado a partir de la especificación de requerimientos

Implementa en Python puro (sin dependencias externas, `decimal` para toda
la aritmética) el ciclo completo de un presupuesto de obra conforme a la
práctica mexicana (Ley de Obras Públicas y Servicios Relacionados con las
Mismas y su Reglamento):

| Módulo | Qué hace | Base normativa / videos |
|---|---|---|
| `modelos` | Catálogo de recursos (8 tipos), matrices de PU con anidación ilimitada, recursos compuestos (cuadrillas/auxiliares), herramienta `%MO`, WBS de agrupadores con niveles ilimitados | videos 4–8, 12–18, 20, 25 |
| `fsr` | Factor de Salario Real: calendario laboral anual, prestaciones, cuotas IMSS/INFONAVIT, ISN opcional, reportes "Factor PS" y "FSR" | Art. 190 RLOPSRM, videos 2 y 21 |
| `costo_horario` | Costo horario de maquinaria: cargos fijos, consumos y operación; modo automático o captura manual | Arts. 194–211, videos 15–16 |
| `indirectos` | Oficina central (porcentaje, anualizado o detallado) y oficina de campo con plantillas de personal y gastos | Art. 180, videos 29–30 |
| `financiamiento` | Flujo de caja: anticipos (totales, sobre materiales o parciales), estimaciones con desfase, tasas activa/pasiva | Art. 183–184, video 32 |
| `utilidad` | Utilidad bruta a partir de la neta deseada protegiendo ISR y PTU | Art. 188, video 33 |
| `pie_precios` | Pie de precios unitarios: cargos en cadena con base directa o acumulable, modo estándar o avanzado con fórmulas | video 28 |
| `generadores` | Números generadores (largo × ancho × alto × piezas) con referencia trazable | video 10 |
| `calendario` | Calendario de trabajo con 4 estados de día y jornadas personalizadas | video 24 |
| `programa` | Programa de obra: fechas sobre días laborables, fraccionamiento de cantidades, ruta crítica (CPM), distribución por día/semana/quincena/mes en cantidades o montos | videos 23, 26 |
| `explosion` | Explosión de insumos con filtros por tipo, desglose opcional del costo horario y programa de suministros por periodo | videos 22, 28 |
| `reportes` | Presupuesto jerárquico, APU, FSR, explosión, suministros, financiamiento (horizontal/vertical); columnas con propiedad "imprimible" y exportación CSV | videos 31, 32, 34–35 |
| `moneda` | Multimoneda con tipo de cambio a moneda base | video 2 |
| `precision` / `formulas` | Decimales configurables por ámbito y evaluador seguro de fórmulas (`"2/20"`, `"1/vida_util"`) | RNF de precisión |

La matriz de trazabilidad requerimiento → módulo está en
[`docs/trazabilidad.md`](docs/trazabilidad.md).

## Requisitos

Python 3.10+. Sin dependencias externas.

## Uso rápido

```python
import invar_calculator as ic

proyecto = ic.Proyecto("Mi obra")

# Recursos y matriz de precio unitario
cemento = proyecto.catalogo.crear("CEM", descripcion="Cemento", unidad="ton", costo=2850)
peon = proyecto.catalogo.registrar(ic.Recurso(
    "PEON", "Peón", "jor", ic.TipoRecurso.MANO_OBRA, salario_base=310))

matriz = proyecto.crear_matriz("MAT-01", "Firme de concreto", "m2")
matriz.agregar_insumo(cemento, "0.02")
matriz.agregar_insumo(peon, "0.15")

# Concepto dentro de la estructura WBS
partida = proyecto.raiz.agregar_agrupador("01", "Albañilería")
partida.agregar_concepto(ic.Concepto("C-01", "Firme 10 cm", "m2", 250, matriz=matriz))

# Sobrecostos y recálculo
proyecto.pie.asignar_porcentaje("IND_OF", 5)
proyecto.pie.asignar_porcentaje("UTIL", 10)
resumen = proyecto.recalcular()
print(resumen.precio_venta, resumen.total_con_iva)
```

## Demostración integral

Construye una obra completa (FSR, cuadrillas, auxiliares, costo horario,
programa de obra, indirectos, financiamiento, utilidad) y emite todos los
reportes:

```bash
python3 demo.py
```

## Pruebas

```bash
python3 -m unittest discover -s tests
```

## Alcance

Este repositorio contiene el **motor de cálculo** (dominio y reportes de
texto/CSV). Los requerimientos de interfaz gráfica de la especificación
(Ribbon, MDI, drag & drop, diseñador WYSIWYG de encabezados, exportación
PDF/XLSX con seguridad) y de infraestructura (SQL Server, migración desde
OPUS 2010/2009, explorador de paramétricos) quedan documentados en la
matriz de trazabilidad como fases posteriores; el diseño del núcleo
(concepto/matriz desacoplados, catálogo con homologación y trazabilidad,
pie de precios por identificadores) está pensado para servirles de base.
