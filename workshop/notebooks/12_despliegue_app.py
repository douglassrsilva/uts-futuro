# Databricks notebook source
# MAGIC %md
# MAGIC # 12 · Desplegar el app (React + FastAPI) sobre lo construido
# MAGIC
# MAGIC Coronamos el workshop desplegando la **app UTS** — una SPA React + backend FastAPI en
# MAGIC **Databricks Apps** — que consume TODO lo que construiste en los notebooks 00-11:
# MAGIC `student_360`, deserción, funil de admisiones, ocupación, Digital Twin, AES, GraphRAG y Genie.
# MAGIC
# MAGIC El código del app vive en la carpeta **`app/`** de este repo (React en `app/frontend/`,
# MAGIC backend FastAPI en `app/server/`). El despliegue es **standalone** (`databricks apps`), **sin
# MAGIC Databricks Asset Bundle** — el app sólo LEE lo que los notebooks ya crearon (tablas vía SQL
# MAGIC Warehouse + model services del AI Gateway + Vector Search + Genie), así que no necesita
# MAGIC pipeline, Lakebase ni recursos de bundle.
# MAGIC
# MAGIC > 🧩 Los pasos de despliegue se ejecutan con la **CLI de Databricks** desde un terminal (no
# MAGIC > desde el notebook), porque compilan el frontend y suben el código. Este notebook te da los
# MAGIC > comandos exactos y verifica los prerrequisitos.

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Prerrequisitos
# MAGIC
# MAGIC - **CLI de Databricks** v0.230+ autenticada a tu workspace (`databricks auth login`).
# MAGIC - **Node.js 18+** (para compilar el frontend React/Vite).
# MAGIC - Los notebooks **00-11** ejecutados en tu catálogo con `schema_prefix=uts` (el app espera
# MAGIC   los schemas `uts_bronze/silver/gold/ml/ops` — ver nota abajo).
# MAGIC - **Databricks Apps** habilitado en tu workspace.
# MAGIC
# MAGIC > ⚠️ **Sobre el `schema_prefix`.** El backend del app tiene los schemas `uts_*` fijados en el
# MAGIC > código (sólo el catálogo es variable, vía `UTS_CATALOG`). Para desplegar el app, ejecuta los
# MAGIC > notebooks 00-11 con **`schema_prefix = uts`** (el valor por defecto). Si usaste otro prefijo
# MAGIC > para aislarte durante el workshop, vuelve a correrlos con `uts` en tu catálogo antes del deploy.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Verificar que la plataforma está lista (lo que el app consume)

# COMMAND ----------

import json
faltan = []
# schemas + tablas gold clave
for t in ("student_360", "dropout_scores", "campus_occupancy", "kg_nodes", "knowledge_chunks", "admissions_funnel"):
    try:
        spark.sql(f"SELECT 1 FROM {GOLD}.{t} LIMIT 1")
    except Exception:
        faltan.append(f"{GOLD}.{t}")
# model services del AI Gateway (uts_ml)
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
try:
    svcs = {s.get("name", "").split("/")[-1] for s in w.api_client.do("GET", "/api/2.1/unity-catalog/model-services").get("model_services", [])}
    for s in (f"{CATALOG}.{PREFIX}_ml.uts-chat-gw", f"{CATALOG}.{PREFIX}_ml.uts-agent-gw",
              f"{CATALOG}.{PREFIX}_ml.uts-aes-judge", f"{CATALOG}.{PREFIX}_ml.uts-embed-gw"):
        if s not in svcs:
            faltan.append(f"model-service {s}")
except Exception as e:
    print(f"(no se pudo listar model-services: {str(e)[:100]})")

if faltan:
    print("⚠️ Faltan estos objetos (ejecuta los notebooks 00-11 primero):")
    for f in faltan:
        print("   -", f)
else:
    print(f"✓ La plataforma está lista en {CATALOG} (prefijo {PREFIX}). Puedes desplegar el app.")

# Genie space (para la variable de entorno del app)
try:
    spaces = w.api_client.do("GET", "/api/2.0/genie/spaces?page_size=100").get("spaces", [])
    genie = next((s for s in spaces if "UTS" in (s.get("title") or "")), None)
    if genie:
        print(f"✓ Genie space: {genie['space_id']}  ('{genie.get('title')}')")
        print("   → úsalo como UTS_GENIE_SPACE_ID / UTS_GENIE_AGENT_ID en app/app.yaml (paso 3).")
    else:
        print("○ Genie space UTS no encontrado (opcional; el notebook 11 lo crea).")
except Exception:
    pass

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Configurar `app/app.yaml` con tus variables de entorno
# MAGIC
# MAGIC El app se configura por **variables de entorno** en `app/app.yaml`. Edita ese archivo con
# MAGIC tus valores (catálogo, warehouse, space de Genie). El backend lee estas variables en runtime
# MAGIC (`app/server/config.py`):
# MAGIC
# MAGIC ```yaml
# MAGIC command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
# MAGIC env:
# MAGIC   - name: DATABRICKS_WAREHOUSE_ID
# MAGIC     value: "<TU_WAREHOUSE_ID>"
# MAGIC   - name: UTS_CATALOG
# MAGIC     value: "<TU_CATALOGO>"
# MAGIC   - name: UTS_GW_CHAT
# MAGIC     value: "<TU_CATALOGO>.uts_ml.uts-chat-gw"
# MAGIC   - name: UTS_GW_AGENT
# MAGIC     value: "<TU_CATALOGO>.uts_ml.uts-agent-gw"
# MAGIC   - name: UTS_GW_JUDGE
# MAGIC     value: "<TU_CATALOGO>.uts_ml.uts-aes-judge"
# MAGIC   - name: UTS_GW_EMBED
# MAGIC     value: "<TU_CATALOGO>.uts_ml.uts-embed-gw"
# MAGIC   - name: UTS_VS_ENDPOINT
# MAGIC     value: "uts-vs"
# MAGIC   - name: UTS_GENIE_SPACE_ID
# MAGIC     value: "<SPACE_ID_del_paso_2>"
# MAGIC   - name: UTS_GENIE_AGENT_ID
# MAGIC     value: "<SPACE_ID_del_paso_2>"
# MAGIC ```
# MAGIC
# MAGIC Abajo generamos el `app.yaml` ya rellenado con TU configuración (cópialo a `app/app.yaml`):

# COMMAND ----------

genie_id = ""
try:
    genie_id = next((s["space_id"] for s in w.api_client.do("GET", "/api/2.0/genie/spaces?page_size=100").get("spaces", []) if "UTS" in (s.get("title") or "")), "")
except Exception:
    pass

app_yaml = f'''command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
env:
  - name: DATABRICKS_WAREHOUSE_ID
    value: "{WAREHOUSE_ID}"
  - name: UTS_CATALOG
    value: "{CATALOG}"
  - name: UTS_GW_CHAT
    value: "{CATALOG}.uts_ml.uts-chat-gw"
  - name: UTS_GW_AGENT
    value: "{CATALOG}.uts_ml.uts-agent-gw"
  - name: UTS_GW_JUDGE
    value: "{CATALOG}.uts_ml.uts-aes-judge"
  - name: UTS_GW_EMBED
    value: "{CATALOG}.uts_ml.uts-embed-gw"
  - name: UTS_VS_ENDPOINT
    value: "uts-vs"
  - name: UTS_GENIE_SPACE_ID
    value: "{genie_id}"
  - name: UTS_GENIE_AGENT_ID
    value: "{genie_id}"
'''
print("──────── copia esto a  app/app.yaml ────────")
print(app_yaml)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Desplegar (ejecutar en un TERMINAL, desde la raíz del repo)
# MAGIC
# MAGIC Con `<PERFIL>` = tu perfil de la CLI:
# MAGIC
# MAGIC ```bash
# MAGIC # 0) Compilar el frontend (genera app/frontend/dist que sirve FastAPI)
# MAGIC cd app/frontend && npm ci && npm run build && cd ../..
# MAGIC
# MAGIC # 1) Crear la app (una sola vez) — crea el compute y el Service Principal
# MAGIC databricks apps create utsfuturo --profile <PERFIL>
# MAGIC
# MAGIC # 2) Subir el código y desplegar (app.yaml ya trae las env vars del paso 3)
# MAGIC databricks sync app "/Workspace/Users/<TU_USUARIO>/utsfuturo-src" --profile <PERFIL>
# MAGIC databricks apps deploy utsfuturo \
# MAGIC   --source-code-path "/Workspace/Users/<TU_USUARIO>/utsfuturo-src" --profile <PERFIL>
# MAGIC ```
# MAGIC
# MAGIC > 💡 Alternativa al `sync`: sube la carpeta `app/` con
# MAGIC > `databricks workspace import-dir app "/Workspace/Users/<TU_USUARIO>/utsfuturo-src" --overwrite`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Conceder permisos al Service Principal del app (al final)
# MAGIC
# MAGIC El SP del app (creado en el paso 4) necesita leer las tablas, ejecutar los model services y
# MAGIC correr Genie. Obtén el SP con `databricks apps get utsfuturo` y ejecuta (en un terminal):
# MAGIC
# MAGIC ```bash
# MAGIC SP=$(databricks apps get utsfuturo --profile <PERFIL> -o json | jq -r .service_principal_client_id)
# MAGIC
# MAGIC # UC: leer catálogo/schemas + volúmenes
# MAGIC databricks api post /api/2.0/sql/statements --profile <PERFIL> --json '{"warehouse_id":"<WH>",
# MAGIC   "statement":"GRANT USE CATALOG ON CATALOG <CAT> TO `'"$SP"'`","wait_timeout":"30s"}'
# MAGIC # (repetir USE SCHEMA + SELECT en uts_gold/silver/ml/ops/bronze; READ VOLUME en documentos/essays)
# MAGIC
# MAGIC # EXECUTE en los model services del AI Gateway
# MAGIC for svc in uts-chat-gw uts-agent-gw uts-aes-judge uts-embed-gw uts-guard-judge; do
# MAGIC   databricks api patch "/api/2.1/unity-catalog/permissions/model_service/<CAT>.uts_ml/$svc" \
# MAGIC     --profile <PERFIL> --json '{"changes":[{"principal":"'"$SP"'","add":["EXECUTE"]}]}'
# MAGIC done
# MAGIC
# MAGIC # CAN_RUN en el Genie space + CAN_USE en el warehouse
# MAGIC databricks api patch "/api/2.0/permissions/genie/<SPACE_ID>" --profile <PERFIL> \
# MAGIC   --json '{"access_control_list":[{"service_principal_name":"'"$SP"'","permission_level":"CAN_RUN"}]}'
# MAGIC ```
# MAGIC
# MAGIC > 🔁 **Reinicia el app** tras conceder permisos (`databricks apps stop/start utsfuturo`): el
# MAGIC > token del SP cachea la config, así que un restart asegura que tome los nuevos grants.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Verificar el despliegue
# MAGIC
# MAGIC ```bash
# MAGIC databricks apps get utsfuturo --profile <PERFIL>          # estado RUNNING + URL
# MAGIC ```
# MAGIC
# MAGIC Abre la URL y prueba:
# MAGIC - `/api/command/kpis` → matrícula, riesgo, deserción
# MAGIC - `/api/genie/mode` → `{"agent_mode":true,"space":true}`
# MAGIC - Vista **Genie**: pregunta "¿Cuántos estudiantes en riesgo hay por campus?"
# MAGIC   - Si ves `modo:"agent"` con razonamiento multi-paso → Deep Research activo (ver notebook 11).
# MAGIC   - Si ves `modo:"clasico"` → respuesta simple (habilita las previews del notebook 11).
# MAGIC
# MAGIC Vistas del app: **Centro de Mando**, **Redacciones (AES)**, **Retención**, **Carreras**,
# MAGIC **Admisiones**, **Campus / Digital Twin**, **Explorador (GraphRAG)** y **Genie**.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎓 ¡Felicidades!
# MAGIC
# MAGIC Construiste, de punta a punta, la plataforma de datos e IA de la **Universidad Tecnológica de
# MAGIC Sudamérica**: datos sintéticos → medallón + DQX → MDM → ML (deserción/propensión/forecast) →
# MAGIC Metric Views → Unity AI Gateway → GraphRAG + Vector Search → Genie → **app agéntico**.
# MAGIC Todo **portable**, **reproducible** y **gobernado**. 🚀

# COMMAND ----------

print("✓ Workshop completo. El código del app está en la carpeta app/ de este repo.")
print("  Reproduce el deploy con los pasos de arriba (standalone, sin bundle).")
