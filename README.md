# 🎓 Workshop · Plataforma de Datos e IA "Universidad Tecnológica de Sudamérica" (UTS)

Construye, **paso a paso y con tus propias manos**, la misma plataforma de datos e IA end-to-end
que impulsa la app UTS: del **dato crudo** de Moodle (LMS) y PeopleSoft Campus Solutions (SIS)
hasta un **app agéntico gobernado** (AES, retención, GraphRAG, Genie, Digital Twin).

Todo el workshop es un conjunto de **notebooks autocontenidos y reproducibles**, parametrizados
con *widgets* (catálogo, prefijo de schema, warehouse) para que **cada participante** pueda
ejecutarlo en su propio espacio sin colisiones.

> Golden demo LATAM · 8 campus en 8 países · 6.000 estudiantes sintéticos · escala 0-20 (LATAM).

---

## 🗺️ ¿Qué vas a construir?

```
  FUENTES           INGESTA           LAKEHOUSE (medallón)         IA / GOBERNANZA        APLICACIÓN
 ┌─────────┐   ┌───────────────┐   ┌──────────────────────┐   ┌─────────────────┐   ┌────────────┐
 │ Moodle  │──▶│ Datos          │──▶│ Bronze (Auto Loader) │──▶│ Unity AI Gateway│──▶│ FastAPI +  │
 │ (LMS)   │   │  sintéticos    │   │ Silver (canónico     │   │  model services │   │ React SPA  │
 │PeopleSoft│  │  → Volúmenes   │   │   HERM/1EdTech + DQX) │   │ ML: deserción   │   │            │
 │ (SIS)   │   │    landing     │   │ Gold (data products, │   │ propensión/fcst │   │ Copiloto   │
 └─────────┘   └───────────────┘   │  Metric Views, grafo)│   │ GraphRAG · Genie│   │ AES·Campus │
                                    └──────────────────────┘   └─────────────────┘   └────────────┘
```

**Principio rector:** Streaming Tables + Materialized Views + Metric Views (no tablas planas).
Cada capa es un objeto gobernado por Unity Catalog, con linaje automático.

---

## 📚 Los notebooks (ejecutar en orden)

| # | Notebook | Qué aprendes | Técnica clave |
|---|----------|--------------|---------------|
| **00** | `00_configuracion` | Widgets, catálogo/schema, creación de schemas y volúmenes | Unity Catalog, `dbutils.widgets` |
| **01** | `01_generacion_datos` | Simular Moodle + PeopleSoft y aterrizar archivos en un Volumen | Datos sintéticos, patrón *landing* |
| **02** | `02_medallion_dqx` | Bronze→Silver→Gold **con gating de calidad DQX inline** | Auto Loader (batch), DQX, cuarentena |
| **03** | `03_dqx_avanzado` | Contratos ODCS, detección de PII, anomalías, PK asistida por LLM | `databricks-labs-dqx[anomaly,llm,datacontract]` |
| **04** | `04_mdm_student360` | Reconciliar el alumno entre SIS y LMS (MDM por email) | Entity resolution, `student_360` |
| **05** | `05_desercion_ml` | Modelo de deserción con explicabilidad, registrado en UC | GradientBoosting + SHAP + **MLflow** |
| **06** | `06_propension` | Propensión de matrícula **anti-leakage** (entrena histórico, scorea activo) | Clasificación + MLflow/UC |
| **07** | `07_forecast` | Proyección de matrícula por campus | Regresión lineal en Spark SQL / AI_FORECAST |
| **08** | `08_metric_views` | Capa semántica gobernada (`MEASURE()`) | Metric Views |
| **09** | `09_ai_gateway` | Hub de gobernanza de IA: model services + guardrail de inyección | Unity AI Gateway (REST Beta) |
| **10** | `10_graphrag_vector_search` | Grafo de conocimiento + Vector Search + recuperación híbrida | GraphRAG, Vector Search |
| **11** | `11_genie` | Espacio Genie sobre el Gold + Agent Mode | Genie / AI-BG |
| **12** | `12_despliegue_app` | Empaquetar y desplegar el app React/FastAPI sobre lo construido | Databricks Asset Bundle, Apps |

Cada notebook empieza con una celda `%md` que explica el **porqué**, ejecuta la lógica en celdas
documentadas y termina con una celda de **verificación** (`assert`/conteos) para que sepas que salió bien.

---

## ⚙️ Requisitos

- Un workspace de **Databricks** con **Unity Catalog** habilitado.
- Permiso `CREATE SCHEMA` (y `CREATE VOLUME`) sobre algún catálogo.
- Un **SQL Warehouse** serverless (para Metric Views, Genie y el app).
- **Serverless compute** para notebooks/jobs (recomendado).
- Para los módulos 09-12: acceso a **Foundation Models**, **Vector Search** y **Databricks Apps**.

> Los módulos 00-08 funcionan en cualquier workspace UC. Los 09-12 usan features de IA/Apps que
> pueden requerir habilitación en tu workspace; cada notebook lo indica y **degrada con gracia**
> si algo no está disponible (nunca rompe el resto del workshop).

---

## 🚀 Cómo empezar

1. **Clona este repo en tu workspace** (Repos → Add Repo → `https://github.com/douglassrsilva/uts-futuro`),
   o importa la carpeta `workshop/` como notebooks.
2. Abre **`00_configuracion`** y ajusta los widgets al inicio:
   - `catalog` — tu catálogo Unity (p. ej. `main` o el tuyo).
   - `schema_prefix` — prefijo de tus schemas (por defecto `uts`; usa algo único como `uts_ana`
     si **compartes catálogo** con otros participantes, para no pisarse).
   - `warehouse_id` — el ID de tu SQL Warehouse.
3. Ejecuta los notebooks **en orden** (00 → 12). Cada uno hereda la configuración vía `%run ./_comun`.

> 💡 **Aislamiento entre participantes.** La forma más limpia es que cada quien use **su propio
> catálogo**. Si eso no es posible, cambien el `schema_prefix` (p. ej. `uts_<nombre>`): todas las
> tablas quedan namespaced y no hay colisiones. El notebook **12 (app)** requiere que el bundle
> apunte a tu catálogo/prefijo — se explica ahí.

---

## 🧱 Conceptos que refuerza el workshop

- **Medallón moderno**: ingestión por Volumen + Auto Loader, capas como Streaming Tables /
  Materialized Views, no tablas ad-hoc.
- **Calidad como *gate*, no como reporte**: DQX aplica reglas bronze→silver y **quarentena** lo
  inválido *al construir* silver (no un chequeo posterior). Contratos **ODCS** como fuente de reglas.
- **Modelo canónico de educación**: HERM + 1EdTech (OneRoster/Caliper) + ISCED-F.
- **MDM**: un alumno, dos sistemas → `student_master_id`.
- **ML con MLflow/UC**: modelos firmados y registrados; anti-leakage explícito en propensión.
- **Gobernanza de IA**: **Unity AI Gateway** como único punto por donde pasa cada llamada LLM, con
  guardrail de **inyección de prompt** sobre entrada no confiable.
- **GraphRAG**: recuperación híbrida (semántica + traversal de grafo) con citas.

---

## ⚠️ Notas y buenas prácticas

- **Solo operaciones aditivas/idempotentes.** Los notebooks usan `CREATE ... IF NOT EXISTS`,
  `CREATE OR REPLACE`, `overwrite`. Puedes re-ejecutarlos: los conteos deben ser estables.
- **Reproducibilidad.** La generación de datos usa `random.seed(42)`; el batch de la medallón
  sobreescribe (no *append*), así no se duplican filas al re-correr.
- **Sin `host` hardcodeado.** Nada asume una URL de workspace concreta; todo sale de tu sesión.
- **Idioma.** Todo el material está en **español** (neutro LATAM). El contenido de la demo (nombres
  de campus, programas, redacciones) también.

---

## 📂 Estructura del repo

```
workshop/
├── README.md                      ← este archivo
├── _comun.py                      ← config compartida (widgets + helpers); se invoca con %run
├── notebooks/
│   ├── 00_configuracion.py
│   ├── 01_generacion_datos.py
│   ├── 02_medallion_dqx.py
│   ├── 03_dqx_avanzado.py
│   ├── 04_mdm_student360.py
│   ├── 05_desercion_ml.py
│   ├── 06_propension.py
│   ├── 07_forecast.py
│   ├── 08_metric_views.py
│   ├── 09_ai_gateway.py
│   ├── 10_graphrag_vector_search.py
│   ├── 11_genie.py
│   └── 12_despliegue_app.py
└── contracts/                     ← contratos de datos ODCS (los usa el módulo 02/03)
    ├── person.odcs.yaml
    └── result.odcs.yaml
```

---

*Workshop derivado de la plataforma UTS (Universidad Tecnológica de Sudamérica), golden demo de
Databricks para educación superior. Todo el material es sintético y ficticio.*
