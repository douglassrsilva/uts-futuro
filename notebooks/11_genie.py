# Databricks notebook source
# MAGIC %md
# MAGIC # 11 · Genie — pregunta en lenguaje natural sobre el Gold
# MAGIC
# MAGIC **Genie** (AI/BI) permite a usuarios de negocio **preguntar en lenguaje natural** ("¿cuántos
# MAGIC estudiantes en riesgo hay por campus?") y obtener SQL + tabla + respuesta, gobernado por Unity
# MAGIC Catalog. El app UTS lo integra en modo **Agent Mode** (investigación multi-paso) con fallback
# MAGIC al Genie clásico.
# MAGIC
# MAGIC En este notebook configuramos un **Genie space** sobre nuestras tablas Gold y lo probamos.
# MAGIC
# MAGIC > 🧭 **Nota.** La creación de Genie spaces por API está evolucionando. La forma **portable y
# MAGIC > recomendada** es declararlo en el **bundle** (`resources.genie_spaces`, ver notebook 12) o
# MAGIC > crearlo desde la **UI** (Genie → New space) apuntando a tus tablas. Aquí intentamos crearlo
# MAGIC > vía API y, si tu workspace no lo permite, te damos los pasos exactos para la UI + cómo
# MAGIC > consultarlo una vez que exista.

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
WAREHOUSE = WAREHOUSE_ID or None

# Las 3 tablas Gold que exponemos a Genie (ordenadas alfabéticamente por identificador,
# requisito del formato serialized_space)
TABLAS = sorted([f"{GOLD}.campus_occupancy", f"{GOLD}.dropout_features", f"{GOLD}.student_360"])

INSTRUCCIONES = [
    "Responde en el idioma de la pregunta (español o portugués).",
    "Las notas están en escala 0-20 (LATAM); gpa es el promedio ponderado.",
    "desercion_label=1 significa estudiante en riesgo de deserción.",
    "gente_trabaja=true identifica a la población que estudia y trabaja.",
    "Audiencia: coordinación académica y rectoría.",
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Crear el Genie space (o instrucciones para la UI)

# COMMAND ----------

serialized = {
    "version": 2,
    "data_sources": {"tables": [{"identifier": t} for t in TABLAS]},
    "instructions": {"text_instructions": [{"content": INSTRUCCIONES}]},
}

space_id = None
try:
    if not WAREHOUSE:
        raise RuntimeError("Configura el widget 'warehouse_id' para crear el Genie space.")
    import json
    resp = w.api_client.do("POST", "/api/2.0/genie/spaces", body={
        "title": f"UTS · Operaciones Académicas ({PREFIX})",
        "warehouse_id": WAREHOUSE,
        "serialized_space": json.dumps(serialized),
    })
    space_id = resp.get("space_id") or resp.get("id")
    print(f"✓ Genie space creado: {space_id}")
except Exception as e:
    print(f"  (No se pudo crear por API: {str(e)[:160]})")
    print("\n  → Créalo desde la UI (2 minutos):")
    print("     1. Menú lateral → Genie → New space.")
    print(f"     2. Warehouse: tu SQL Warehouse serverless.")
    print(f"     3. Tablas: {', '.join(TABLAS)}")
    print("     4. Instrucciones (pégalas en 'General instructions'):")
    for i in INSTRUCCIONES:
        print(f"        · {i}")
    print("     5. Copia el space_id de la URL (…/genie/rooms/<space_id>) y ponlo abajo.")

# Si lo creaste por UI, pega aquí el space_id para probarlo:
# space_id = "01f........"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Preguntar a Genie (start-conversation + poll)
# MAGIC
# MAGIC El patrón clásico: iniciar conversación con la pregunta y hacer *poll* del mensaje hasta que
# MAGIC esté `COMPLETED`. Genie devuelve texto (y el SQL que generó, en los `attachments`).

# COMMAND ----------

def preguntar_genie(space_id, pregunta, timeout_s=60):
    import time
    start = w.api_client.do("POST", f"/api/2.0/genie/spaces/{space_id}/start-conversation",
                            body={"content": pregunta})
    cid, mid = start["conversation_id"], start["message_id"]
    m = {}
    for _ in range(timeout_s // 2):
        m = w.api_client.do("GET", f"/api/2.0/genie/spaces/{space_id}/conversations/{cid}/messages/{mid}")
        if m.get("status") == "COMPLETED":
            break
        time.sleep(2)
    texto = "".join(a.get("text", {}).get("content", "") for a in m.get("attachments", []))
    sql = "".join(a.get("query", {}).get("query", "") for a in m.get("attachments", []) if a.get("query"))
    return texto, sql

if space_id:
    texto, sql = preguntar_genie(space_id, "¿Cuántos estudiantes hay en total?")
    print("RESPUESTA:", texto or "(sin texto)")
    print("\nSQL generado:\n", sql or "(no expuesto)")
else:
    print("Configura space_id (creado por API o UI) para ejecutar esta prueba.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Agent Mode (Beta) — investigación multi-paso
# MAGIC
# MAGIC El app UTS usa el **Agent Mode**, donde Genie razona, ejecuta **varias** consultas y sintetiza
# MAGIC un informe con citas. La llamada es a `/api/2.0/genie/agents/{space_id}/responses`. El código
# MAGIC del app (`app/server/routes/genie.py`) maneja tanto Agent Mode como el fallback clásico de
# MAGIC arriba. Referencia del cuerpo:
# MAGIC
# MAGIC ```python
# MAGIC body = {"input": [{"type": "message", "role": "user",
# MAGIC                    "content": [{"type": "input_text", "text": pregunta}]}], "stream": False}
# MAGIC w.api_client.do("POST", f"/api/2.0/genie/agents/{space_id}/responses", body=body)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Verificación

# COMMAND ----------

if space_id:
    print(f"✓ Genie space {space_id} operativo sobre {len(TABLAS)} tablas Gold.")
    print(f"  Guárdalo: lo usarás como UTS_GENIE_SPACE_ID en el notebook 12 (app).")
else:
    print("○ Genie pendiente de crear (API o UI). Anota el space_id para el notebook 12.")
print("\nTablas expuestas a Genie:")
for t in TABLAS:
    print(f"  · {t}")
