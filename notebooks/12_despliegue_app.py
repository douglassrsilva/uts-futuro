# Databricks notebook source
# MAGIC %md
# MAGIC # 12 · Desplegar el app (React + FastAPI) sobre lo construido
# MAGIC
# MAGIC Coronamos el workshop desplegando la **app UTS** — una SPA React + backend FastAPI en
# MAGIC **Databricks Apps** — que consume TODO lo que construiste: `student_360`, deserción, funil de
# MAGIC admisiones, ocupación, Digital Twin, AES, GraphRAG y Genie.
# MAGIC
# MAGIC El código del app y su empaquetado (**Databricks Asset Bundle**) ya viven en el repo
# MAGIC (`app/` y `resources/`). Este notebook explica cómo **apuntarlos a TU catálogo/prefijo** y
# MAGIC desplegar. El deploy real se hace con la **CLI de Databricks** desde tu máquina o un terminal
# MAGIC (no desde el notebook), porque compila el frontend y sube el bundle.
# MAGIC
# MAGIC > 🧩 A diferencia de los notebooks 00-11 (que corren en el workspace), este paso usa la **CLI**.
# MAGIC > Abajo tienes los comandos exactos.

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Requisitos del app
# MAGIC
# MAGIC - **CLI de Databricks** v0.230+ autenticada a tu workspace (`databricks auth login`).
# MAGIC - **Node.js 18+** (para compilar el frontend React/Vite).
# MAGIC - Las tablas Gold + los model services del AI Gateway (notebooks 00-10) ya creados en tu
# MAGIC   catálogo/prefijo.
# MAGIC - Un **Genie space** (notebook 11) — opcional pero recomendado (la vista Genie).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Apuntar el bundle a TU catálogo
# MAGIC
# MAGIC El bundle (`databricks.yml` en la raíz del repo) define una variable `catalog`. Todo el app
# MAGIC lee sus schemas de ahí. El bundle asume el prefijo `uts_` (schemas `uts_gold`, `uts_ml`, …).
# MAGIC
# MAGIC > ⚠️ **Sobre el `schema_prefix`.** Si en el workshop usaste un prefijo distinto (p. ej.
# MAGIC > `uts_ana`), el app —que espera `uts_*`— no encontrará tus tablas. Para desplegar el app,
# MAGIC > lo más simple es **usar el prefijo por defecto `uts`** (re-ejecuta los notebooks 00-10 con
# MAGIC > `schema_prefix = uts` en tu catálogo). Así el bundle y tus datos coinciden sin editar código.

# COMMAND ----------

print("Para el despliegue del app, usa esta configuración en el bundle:\n")
print(f"  Catálogo (--var catalog=) : {CATALOG}")
print(f"  Schemas esperados por el app: {CATALOG}.uts_bronze / uts_silver / uts_gold / uts_ml / uts_ops")
print(f"  Warehouse (--var warehouse_id=): {WAREHOUSE_ID or '(configura tu warehouse)'}")
if PREFIX != "uts":
    print(f"\n  ⚠ Tu schema_prefix del workshop es '{PREFIX}', pero el app espera 'uts'.")
    print(f"    Re-ejecuta los notebooks 00-10 con schema_prefix=uts en {CATALOG} antes de desplegar.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Comandos de despliegue (ejecutar en un TERMINAL, no aquí)
# MAGIC
# MAGIC Desde la raíz del repo clonado, con `<PERFIL>` = tu perfil de la CLI y `<CAT>` = tu catálogo:
# MAGIC
# MAGIC ```bash
# MAGIC # 0) Compilar el frontend (genera app/frontend/dist que sirve FastAPI)
# MAGIC cd app/frontend && npm install && npm run build && cd ../..
# MAGIC
# MAGIC # 1) Validar y desplegar el bundle (schemas, volúmenes, pipeline, job, VS, lakebase, genie, app)
# MAGIC databricks bundle validate --profile <PERFIL> --var catalog=<CAT> --var warehouse_id=<WH>
# MAGIC databricks bundle deploy   --profile <PERFIL> --var catalog=<CAT> --var warehouse_id=<WH>
# MAGIC
# MAGIC # 2) (Opcional) Ejecutar el job de datos si NO usaste los notebooks — reproduce nb 01-08:
# MAGIC #    databricks bundle run uts_build --profile <PERFIL> --var catalog=<CAT>
# MAGIC
# MAGIC # 3) Crear los model services del AI Gateway (si no corriste el notebook 09):
# MAGIC #    python3 src/ml/aigw_foundation_models.py --catalog <CAT>
# MAGIC
# MAGIC # 4) Desplegar/arrancar el app (crea su Service Principal)
# MAGIC databricks bundle run utsfuturo --profile <PERFIL> --var catalog=<CAT>
# MAGIC
# MAGIC # 5) Conceder permisos al SP del app (UC + EXECUTE en services + Genie CAN_RUN) — SIEMPRE al final
# MAGIC python3 setup/grant_app_access.py --profile <PERFIL> --catalog <CAT> --warehouse <WH>
# MAGIC ```
# MAGIC
# MAGIC O, en un solo paso, el script orquestador del repo:
# MAGIC
# MAGIC ```bash
# MAGIC PROFILE=<PERFIL> CATALOG=<CAT> WAREHOUSE=<WH> ./setup.sh
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Conectar Genie al app
# MAGIC
# MAGIC El app lee el Genie space de una variable de entorno. En `resources/app.yml`, el enlace se
# MAGIC hace por **recurso** (no por interpolación de `.id`, que no resuelve en `config.env`):
# MAGIC
# MAGIC ```yaml
# MAGIC config:
# MAGIC   env:
# MAGIC     - name: UTS_GENIE_SPACE_ID
# MAGIC       value_from: genie-space        # ← lee el space del recurso enlazado
# MAGIC     - name: UTS_GENIE_AGENT_ID
# MAGIC       value_from: genie-space
# MAGIC resources:
# MAGIC   - name: genie-space
# MAGIC     genie_space:
# MAGIC       name: "UTS · Operaciones Académicas"
# MAGIC       space_id: ${resources.genie_spaces.uts_academico.id}
# MAGIC       permission: CAN_RUN
# MAGIC ```
# MAGIC
# MAGIC > 💡 Lección aprendida: `value: ${resources.genie_spaces.<x>.id}` en `config.env` queda
# MAGIC > **literal** (no resuelve) → el app arranca con Genie vacío. Usa `value_from: <recurso>`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Verificar el despliegue
# MAGIC
# MAGIC ```bash
# MAGIC databricks apps get utsfuturo --profile <PERFIL>          # estado RUNNING + URL
# MAGIC # abre la URL y prueba: /api/genie/mode → {"agent_mode":true,"space":true}
# MAGIC ```
# MAGIC
# MAGIC El app expone las vistas: **Centro de Mando**, **Redacciones (AES)**, **Retención**,
# MAGIC **Carreras**, **Admisiones**, **Campus / Digital Twin**, **Explorador (GraphRAG)** y **Genie**.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎓 ¡Felicidades!
# MAGIC
# MAGIC Construiste, de punta a punta, la plataforma de datos e IA de la **Universidad Tecnológica de
# MAGIC Sudamérica**:
# MAGIC
# MAGIC - **Datos** sintéticos de Moodle + PeopleSoft → **medallón** con **calidad DQX** como gate.
# MAGIC - **MDM** (`student_360`), **modelo canónico** HERM/1EdTech.
# MAGIC - **ML** con MLflow/UC: deserción (SHAP), propensión (anti-leakage), forecast.
# MAGIC - **Capa semántica** (Metric Views).
# MAGIC - **Gobernanza de IA** con Unity AI Gateway + guardrail de inyección.
# MAGIC - **GraphRAG** (grafo + Vector Search) y **Genie**.
# MAGIC - Un **app agéntico** que lo pone todo en manos del usuario.
# MAGIC
# MAGIC Todo **portable** (brick DAB), **reproducible** y **gobernado**. 🚀

# COMMAND ----------

print("✓ Workshop completo. Revisa el README para el mapa de módulos y comparte tu app desplegada.")
