# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · DQX avanzado — contratos, PII, anomalías y PK asistida por LLM
# MAGIC
# MAGIC En el notebook 02 usamos DQX como **gate** (bronze→silver + cuarentena). Aquí exploramos las
# MAGIC capacidades de **discovery / profiling** de DQX, que corren *sobre las tablas ya
# MAGIC materializadas* y escriben reportes en el schema `*_ops` (observabilidad de calidad):
# MAGIC
# MAGIC | Capacidad | Qué hace |
# MAGIC |---|---|
# MAGIC | **Contratos ODCS** | Documentar qué reglas rigen (generadas del contrato) |
# MAGIC | **Detección de PII** | Marcar columnas con datos personales (`does_not_contain_pii`) |
# MAGIC | **Row-level Anomaly Detection** | Entrenar un modelo y detectar filas atípicas |
# MAGIC | **AI-assisted Primary Key** | Descubrir la clave primaria con ayuda de un LLM |
# MAGIC
# MAGIC > 🧱 **Diseño robusto:** cada capacidad va en su propio `try/except`. Si un extra opcional no
# MAGIC > está instalado (p. ej. `[anomaly]` requiere `shap`), esa sección se salta con un mensaje y
# MAGIC > **las demás siguen**. Nunca rompe el workshop.
# MAGIC
# MAGIC **Diferencia clave con el gating:** esto NO barra el dato malo (eso ya lo hizo el pipeline);
# MAGIC **descubre y documenta** características de calidad para la vista de observabilidad.

# COMMAND ----------

# MAGIC %pip install "databricks-labs-dqx[anomaly,llm,datacontract]"
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

import json, datetime, os
from databricks.sdk import WorkspaceClient
ws = WorkspaceClient()
_now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()

def guardar_reporte(nombre, filas, schema):
    """Escribe (overwrite idempotente) un reporte en *_ops. Si no hay filas, crea tabla vacía tipada."""
    df = spark.createDataFrame(filas or [], schema)
    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{OPS}.{nombre}")
    print(f"  {OPS}.{nombre}: {len(filas or [])} filas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Resumen de cuarentena
# MAGIC
# MAGIC Documentamos cuántas filas quedaron válidas vs en cuarentena en el gating del notebook 02.
# MAGIC Es la métrica de salud de la calidad que verá la vista de observabilidad.

# COMMAND ----------

rows = []
for valid_t, q_t in [("person", "quarantine_person"), ("result", "quarantine_result")]:
    try:
        v = spark.table(f"{SILVER}.{valid_t}").count()
    except Exception:
        v = -1
    try:
        q = spark.table(f"{SILVER}.{q_t}").count()
    except Exception:
        q = -1
    tasa = round(q / (v + q) * 100, 2) if v >= 0 and q >= 0 and (v + q) > 0 else 0.0
    rows.append((valid_t, int(v), int(q), float(tasa), _now()))
    print(f"  {valid_t}: válidos={v} cuarentena={q} ({tasa}%)")
guardar_reporte("dq_quarantine_summary", rows,
    "tabla string, validos int, cuarentena int, tasa_cuarentena_pct double, generado_ts string")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Contratos ODCS — reporte de reglas
# MAGIC
# MAGIC Generamos las reglas desde los contratos ODCS (misma fuente que el gating) y las
# MAGIC **documentamos** en una tabla, para que la vista de calidad muestre "qué reglas rigen".

# COMMAND ----------

def _contract_dir():
    for cand in ("../contracts", "contracts", os.path.join(os.getcwd(), "contracts")):
        if os.path.isdir(cand):
            return cand
    return ""

rows = []
cdir = _contract_dir()
try:
    from databricks.labs.dqx.profiler.generator import DQGenerator
    gen = DQGenerator(workspace_client=ws, spark=spark)
    files = [f for f in (os.listdir(cdir) if cdir else []) if f.endswith((".yaml", ".yml"))]
    for cf in files:
        try:
            reglas = gen.generate_rules_from_contract(contract_file=os.path.join(cdir, cf))
            for r in reglas:
                ck = r.get("check", {}) or {}
                rows.append((cf, r.get("name", ""), r.get("criticality", "error"),
                             ck.get("function", ""), json.dumps(ck.get("arguments", {}))[:300], _now()))
            print(f"  {cf}: {len(reglas)} reglas")
        except Exception as e:
            rows.append((cf, "ERROR", "warn", "generation_failed", str(e)[:280], _now()))
except Exception as e:
    print(f"  (DQGenerator no disponible: {str(e)[:100]}) — el pipeline usa su fallback a mano")
guardar_reporte("dq_contract_rules", rows,
    "contrato string, regla string, criticidad string, funcion string, argumentos string, generado_ts string")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Detección de PII
# MAGIC
# MAGIC DQX puede marcar columnas que contienen **información personal** con la check
# MAGIC `does_not_contain_pii` (usa `presidio`). Sobre `person`, columnas como `nombre` y `documento`
# MAGIC son PII por naturaleza.
# MAGIC
# MAGIC > 🔎 **Lección de gobernanza (importante).** En un **sistema de información estudiantil**, los
# MAGIC > nombres y documentos **son el dato legítimo del negocio** — aparecen en cada ficha, carta y
# MAGIC > redacción. Por eso NO se *bloquean*: la detección de PII sirve para **catalogar y gobernar
# MAGIC > el acceso** (grants/ABAC en Unity Catalog, enmascaramiento por rol), no para rechazar filas.
# MAGIC > Aquí sólo la marcamos como advertencia (`warn`) para el catálogo de calidad.

# COMMAND ----------

rows = []
try:
    import presidio_analyzer  # señal de que el extra [pii] está disponible
    from databricks.labs.dqx.engine import DQEngine
    dq = DQEngine(ws)
    checks = [{"name": f"pii_{c}", "criticality": "warn",
               "check": {"function": "does_not_contain_pii", "arguments": {"column": c, "threshold": 0.6}}}
              for c in ("nombre", "documento")]
    person = spark.table(f"{SILVER}.person")
    marcado = dq.apply_checks_by_metadata(person, checks)
    from pyspark.sql import functions as F
    con_pii = marcado.filter(F.col("_warnings").isNotNull() & (F.size(F.col("_warnings")) > 0)).count()
    total = person.count()
    for c in ("nombre", "documento"):
        rows.append(("person", c, "warn", "does_not_contain_pii", int(total), _now()))
    print(f"  PII marcada en person.nombre y person.documento ({con_pii}/{total} filas con señal PII)")
except Exception as e:
    print(f"  (detección de PII no disponible — extra [pii]/presidio: {str(e)[:120]})")
    for c in ("nombre", "documento"):
        rows.append(("person", c, "warn", "does_not_contain_pii (no ejecutado)", -1, _now()))
guardar_reporte("dq_pii_report", rows,
    "tabla string, columna string, criticidad string, funcion string, filas_total int, generado_ts string")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Row-level Anomaly Detection
# MAGIC
# MAGIC DQX puede **entrenar un modelo de detección de anomalías** sobre columnas numéricas y luego
# MAGIC marcar filas atípicas (aquí, umbral percentil 97). Útil para detectar registros académicos
# MAGIC "raros" (combinaciones improbables de GPA/créditos/mora). Requiere el extra `[anomaly]` (shap).

# COMMAND ----------

rows = []
model_name = f"{ML.split('.')[-1]}_dq_anomaly"
model_fq = f"{ML}.uts_dq_anomaly"
registry = f"{ML}.dqx_anomaly_models"
try:
    from databricks.labs.dqx.anomaly.anomaly_engine import AnomalyEngine
    from databricks.labs.dqx.engine import DQEngine
    from databricks.labs.dqx.rule import DQDatasetRule
    from databricks.labs.dqx.anomaly.check_funcs import has_no_row_anomalies
    from pyspark.sql import functions as F

    feat = spark.sql(f"""
        SELECT t.student_id, t.gpa, t.creditos_acum, t.cursos_inscritos,
               COALESCE(f.dias_mora,0) AS dias_mora, COALESCE(f.saldo_vencido,0.0) AS saldo_vencido
        FROM {SILVER}.academic_term t
        LEFT JOIN {SILVER}.financial_account f ON t.student_id = f.student_id""").na.drop()

    ae = AnomalyEngine(ws)
    ae.train(df=feat, model_name=model_fq, registry_table=registry,
             columns=["gpa", "creditos_acum", "cursos_inscritos", "dias_mora", "saldo_vencido"])
    rule = DQDatasetRule(criticality="warn", check_func=has_no_row_anomalies,
                         check_func_kwargs={"model_name": model_fq, "registry_table": registry,
                                            "threshold": 97.0, "enable_ai_explanation": False,
                                            "enable_contributions": False})
    scored = DQEngine(ws, spark).apply_checks(feat, [rule])
    total = feat.count()
    try:
        anom = scored.filter(F.col("_warnings").cast("string").contains("anomal")).count()
    except Exception:
        anom = -1
    rows.append(("uts_dq_anomaly", "academic_term+financial", int(total), int(anom), 97.0, model_fq, _now()))
    print(f"  anomalías: {anom}/{total} filas atípicas (umbral p97)")
except Exception as e:
    print(f"  (Anomaly detection no disponible/falló: {str(e)[:160]})")
    rows.append(("uts_dq_anomaly", "no_disponible", -1, -1, 97.0, str(e)[:120], _now()))
guardar_reporte("dq_anomaly_report", rows,
    "modelo string, dataset string, filas_total int, filas_anomalas int, umbral_pct double, detalle string, generado_ts string")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. AI-assisted Primary Key detection
# MAGIC
# MAGIC `DQProfiler.detect_primary_keys_with_llm` usa un LLM para **inferir qué columnas forman la
# MAGIC clave primaria** de una tabla (útil al perfilar datasets desconocidos). Lo corremos sobre las
# MAGIC tablas silver. Requiere el extra `[llm]`.

# COMMAND ----------

rows = []
tablas = ["person", "result", "academic_term", "financial_account", "enrollment", "course_offering"]
try:
    from databricks.labs.dqx.profiler.profiler import DQProfiler
    from databricks.labs.dqx.config import InputConfig
    prof = DQProfiler(workspace_client=ws, spark=spark)
    for t in tablas:
        try:
            res = prof.detect_primary_keys_with_llm(input_config=InputConfig(location=f"{SILVER}.{t}"))
            if not isinstance(res, dict):
                res = getattr(res, "__dict__", {}) or {}
            pk = res.get("primary_key_columns") or res.get("primary_keys") or res.get("columns") or []
            conf = res.get("confidence", res.get("confidence_score", res.get("score", None)))
            reason = res.get("reasoning", res.get("explanation", ""))
            rows.append((t, json.dumps(pk), float(conf) if isinstance(conf, (int, float)) else -1.0, str(reason)[:500], _now()))
            print(f"  {t}: PK={pk} (conf={conf})")
        except Exception as e:
            rows.append((t, "[]", -1.0, f"error: {str(e)[:200]}", _now()))
            print(f"  {t}: fallo → {str(e)[:100]}")
except Exception as e:
    print(f"  (DQProfiler LLM no disponible: {str(e)[:160]})")
    rows.append(("<n/a>", "[]", -1.0, str(e)[:200], _now()))
guardar_reporte("dq_pk_detection", rows,
    "tabla string, primary_key string, confianza double, razonamiento string, generado_ts string")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Verificación

# COMMAND ----------

reportes = {r.tableName for r in spark.sql(f"SHOW TABLES IN {OPS}").collect()}
print(f"✓ Reportes de calidad en {OPS}: {sorted(reportes)}")
print("\nResumen de cuarentena:")
display(spark.table(f"{OPS}.dq_quarantine_summary"))
