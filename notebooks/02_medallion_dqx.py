# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Medallón (Bronze → Silver → Gold) con calidad DQX
# MAGIC
# MAGIC Construimos la arquitectura **medallón** sobre los archivos que aterrizamos en el notebook 01,
# MAGIC aplicando **calidad de datos como *gate*** (no como reporte posterior):
# MAGIC
# MAGIC | Capa | Qué es | En este workshop |
# MAGIC |---|---|---|
# MAGIC | **Bronze** | Datos crudos ingeridos | Lectura de los CSV de `landing` → tablas Delta |
# MAGIC | **Silver** | Modelo **canónico** (HERM/1EdTech) + **DQX** | Tipado + reglas de calidad + **cuarentena** |
# MAGIC | **Gold** | Data products listos para consumo | `student_360`, features, ocupación, grafo, chunks |
# MAGIC
# MAGIC > 🏗️ **Nota sobre la implementación.** La plataforma UTS de producción usa **Spark Declarative
# MAGIC > Pipelines (SDP/Lakeflow)** con **Streaming Tables** (Auto Loader) y **Materialized Views**.
# MAGIC > Aquí lo hacemos en **batch, celda a celda**, para que veas *toda* la transformación y la
# MAGIC > calidad por dentro. El resultado (las mismas tablas Silver/Gold) es equivalente. Al final
# MAGIC > mostramos cómo se vería la versión declarativa.
# MAGIC
# MAGIC **DQX** (`databricks-labs-dqx`) es la librería de calidad de datos de Databricks Labs. La idea
# MAGIC central del medallón: **la calidad se aplica al construir Silver**, quarentenando lo inválido.

# COMMAND ----------

# MAGIC %pip install databricks-labs-dqx
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. BRONZE — ingerir los CSV crudos
# MAGIC
# MAGIC Leemos cada carpeta de `landing/` y la materializamos como tabla Delta en el schema bronze,
# MAGIC **sin transformar** (crudo fiel a la fuente). Usamos `overwrite` → re-ejecutable sin duplicar.
# MAGIC
# MAGIC > En producción, esto es una **Streaming Table** con Auto Loader:
# MAGIC > `spark.readStream.format("cloudFiles").option("cloudFiles.format","csv")...` — ingesta
# MAGIC > incremental automática. En batch, un `spark.read.csv` + `saveAsTable` logra el equivalente
# MAGIC > para el workshop.

# COMMAND ----------

# esquemas explícitos (evita inferencia frágil y fija los tipos desde bronze)
BRONZE_SCHEMAS = {
    "ps_personal_data": "emplid string, nombre string, documento string, email string, anio_nac int, genero string, pais string, load_ts string",
    "ps_acad_prog": "emplid string, acad_prog string, prog_nombre string, isced_f string, campus string, ingreso_anio int, prog_status string",
    "ps_stdnt_car_term": "emplid string, strm string, gpa double, creditos_acum int, gente_trabaja int, cursos_inscritos int, semestre int",
    "ps_student_fin": "emplid string, strm string, mensualidad double, dias_mora int, saldo_vencido double",
    "ps_adm_appl_data": "appl_id string, campus string, pais string, acad_prog string, prog_nombre string, canal string, puntaje_admision double, etapa_funil string, ciclo_admision int",
    "campus_geo": "campus_id string, ciudad string, pais string, pais_nombre string, moneda string, lat double, lon double, vertical string, mensualidad_usd int, es_sede int",
    "campus_capacity": "campus_id string, salas_capacidad int, alumnos_por_sala int, energia_kwh_capacidad int, kwh_por_alumno double, comedor_capacidad int, comidas_por_alumno double, labs_capacidad int, alumnos_por_lab int, camas_capacidad int, ratio_dormitorio double, n_inicial int, n_media int, n_final int",
    "matricula_historica": "campus_id string, pais string, strm string, periodo_idx int, matricula int",
    "paper_catalog": "paper_id string, titulo string, autores string, anio int, isced_f string, abstract string, pdf_path string, citas int",
    "essay_submissions": "essay_id string, student_id string, tema string, tipo string, archivo string, texto_ocr string, nota_humana double, estado string",
    "essay_rubric": "criterio_id string, criterio string, descriptor string, peso int",
    "mdl_course": "courseid int, shortname string, fullname string, prereq string, term string",
    "mdl_user": "userid int, firstname string, lastname string, email string, load_ts string",
    "mdl_user_enrolments": "userid int, courseid int, timeenrolled string, role string",
    "mdl_assign": "assignid int, courseid int, name string, tipo string, duedate string",
    "mdl_assign_submission": "assignid int, userid int, timemodified string, status string, longitud int",
    "mdl_grades": "assignid int, userid int, courseid int, nota double, timemodified string",
    "mdl_logstore_standard_log": "userid int, courseid int, action string, target string, timecreated string",
}

for tabla, schema in BRONZE_SCHEMAS.items():
    (spark.read.option("header", "true").schema(schema).csv(f"{LANDING}/{tabla}")
        .write.mode("overwrite").option("overwriteSchema", "true")
        .saveAsTable(f"{BRONZE}.bronze_{tabla}"))
print(f"✓ {len(BRONZE_SCHEMAS)} tablas bronze materializadas en {BRONZE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Reglas de calidad DQX — desde contratos ODCS
# MAGIC
# MAGIC **Open Data Contract Standard (ODCS)** es un estándar para declarar el "contrato" de un
# MAGIC dataset (schema, calidad, semántica) en YAML. DQX puede **generar reglas de calidad
# MAGIC automáticamente** desde un contrato ODCS con `DQGenerator`.
# MAGIC
# MAGIC Los contratos viven en `workshop/contracts/` (`person.odcs.yaml`, `result.odcs.yaml`). Si el
# MAGIC extra `[datacontract]` no está disponible en tu runtime, usamos un **fallback** de reglas
# MAGIC equivalentes escritas a mano — el workshop no se rompe.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.labs.dqx.engine import DQEngine
_ws = WorkspaceClient()
dq = DQEngine(_ws)

# Ubicar la carpeta de contratos (relativa al notebook, dentro del repo clonado)
import os
def _contract_path(fname):
    for cand in (f"../contracts/{fname}", f"contracts/{fname}",
                 os.path.join(os.getcwd(), "contracts", fname)):
        if os.path.isfile(cand):
            return cand
    return ""

def reglas_desde_contrato(fname, fallback):
    path = _contract_path(fname)
    if path:
        try:
            from databricks.labs.dqx.profiler.generator import DQGenerator
            gen = DQGenerator(workspace_client=_ws, spark=spark)
            rules = gen.generate_rules_from_contract(contract_file=path)
            if rules:
                print(f"  DQX: {len(rules)} reglas generadas desde el contrato {fname}")
                return rules
        except Exception as e:
            print(f"  DQX: contrato {fname} no generó reglas ({str(e)[:100]}) → fallback a mano")
    else:
        print(f"  DQX: contrato {fname} no encontrado → fallback a mano")
    return fallback

# Fallback equivalente al contrato person.odcs.yaml (8 países LATAM)
PERSON_FALLBACK = [
    {"name": "student_present", "criticality": "error", "check": {"function": "is_not_null", "arguments": {"column": "student_id"}}},
    {"name": "email_present", "criticality": "error", "check": {"function": "is_not_null", "arguments": {"column": "email"}}},
    {"name": "email_formato", "criticality": "warn", "check": {"function": "is_valid_email", "arguments": {"column": "email"}}},
    # país en la lista de 8 países LATAM. Usamos `sql_expression` (portable entre versiones de DQX)
    # en vez de `is_in_list`: en DQX 0.16.x el deserializador de metadata resuelve los valores de
    # `allowed` como NOMBRES DE COLUMNA (['PE',...] → error "column PE cannot be resolved").
    {"name": "pais_valido", "criticality": "warn", "check": {"function": "sql_expression", "arguments": {"expression": "pais IN ('PE','CL','CO','EC','BO','MX','BR','AR','UY')", "msg": "país fuera de la lista LATAM", "name": "pais_valido"}}},
]
RESULT_FALLBACK = [
    {"name": "nota_en_rango", "criticality": "error", "check": {"function": "is_in_range", "arguments": {"column": "nota", "min_limit": 0.0, "max_limit": 20.0}}},
]

PERSON_CHECKS = reglas_desde_contrato("person.odcs.yaml", PERSON_FALLBACK)
RESULT_CHECKS = reglas_desde_contrato("result.odcs.yaml", RESULT_FALLBACK)
print(f"✓ Reglas listas: person={len(PERSON_CHECKS)} · result={len(RESULT_CHECKS)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Semántica del *gating*: errores → cuarentena; advertencias → anotar
# MAGIC
# MAGIC DQX marca cada fila con dos columnas: `_errors` (reglas `criticality=error`) y `_warnings`
# MAGIC (reglas `criticality=warn`). El helper `get_valid()` de DQX descarta filas con errores **o**
# MAGIC advertencias — pero para el medallón queremos algo más matizado:
# MAGIC
# MAGIC - **Errores duros** (p. ej. `student_id` nulo) → van a la tabla **cuarentena**.
# MAGIC - **Advertencias** (p. ej. email con formato dudoso) → **pasan a Silver, anotadas**.
# MAGIC
# MAGIC Por eso definimos nuestros propios filtros sobre la columna `_errors`.

# COMMAND ----------

from pyspark.sql import functions as F

def validos_sin_errores(dqx_df):
    """Silver = filas SIN errores duros (las advertencias pasan)."""
    keep = dqx_df.filter(F.col("_errors").isNull() | (F.size(F.col("_errors")) == 0))
    return keep.drop("_errors", "_warnings")

def solo_errores(dqx_df):
    """Cuarentena = sólo filas con errores duros (criticality=error)."""
    return dqx_df.filter(F.col("_errors").isNotNull() & (F.size(F.col("_errors")) > 0))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. SILVER — modelo canónico + DQX
# MAGIC
# MAGIC Transformamos bronze al **modelo canónico** de educación superior:
# MAGIC - **HERM** (Higher Education Reference Model) para persona, programa, término, finanzas.
# MAGIC - **1EdTech OneRoster** para cursos, matrículas, notas (`result`).
# MAGIC - **1EdTech Caliper** para eventos de aprendizaje.
# MAGIC - **ISCED-F** como taxonomía de áreas de conocimiento.
# MAGIC
# MAGIC Las tablas `person` y `result` pasan por **DQX**: producimos la tabla válida + su
# MAGIC `quarantine_*`.

# COMMAND ----------

# --- person (HERM) con DQX ---
person_src = spark.table(f"{BRONZE}.bronze_ps_personal_data").selectExpr(
    "emplid AS student_id", "nombre", "documento", "email", "anio_nac", "genero", "pais")
person_dqx = dq.apply_checks_by_metadata(person_src, PERSON_CHECKS)
validos_sin_errores(person_dqx).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SILVER}.person")
solo_errores(person_dqx).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SILVER}.quarantine_person")

# --- program (HERM + ISCED-F) ---
spark.table(f"{BRONZE}.bronze_ps_acad_prog").selectExpr(
    "emplid AS student_id", "acad_prog AS program_id", "prog_nombre AS program_name",
    "isced_f", "campus AS campus_id", "ingreso_anio", "prog_status"
).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SILVER}.program")

# --- academic_term (HERM) ---
spark.table(f"{BRONZE}.bronze_ps_stdnt_car_term").selectExpr(
    "emplid AS student_id", "strm AS term", "gpa", "creditos_acum",
    "CAST(gente_trabaja AS BOOLEAN) AS gente_trabaja", "cursos_inscritos", "semestre"
).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SILVER}.academic_term")

# --- financial_account (HERM) ---
spark.table(f"{BRONZE}.bronze_ps_student_fin").selectExpr(
    "emplid AS student_id", "strm AS term", "mensualidad", "dias_mora", "saldo_vencido"
).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SILVER}.financial_account")

# --- course_offering (OneRoster) ---
spark.table(f"{BRONZE}.bronze_mdl_course").selectExpr(
    "courseid AS course_sourced_id", "shortname AS course_code",
    "fullname AS course_title", "NULLIF(prereq,'') AS prereq_code", "term"
).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SILVER}.course_offering")

# --- enrollment (OneRoster) ---
_e = spark.table(f"{BRONZE}.bronze_mdl_user_enrolments")
_u = spark.table(f"{BRONZE}.bronze_mdl_user").select("userid", "email")
_e.join(_u, "userid").selectExpr(
    "userid AS student_moodle_id", "email", "courseid AS course_sourced_id",
    "timeenrolled AS enrolled_at", "role"
).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SILVER}.enrollment")

# --- result (OneRoster) con DQX ---
_g = spark.table(f"{BRONZE}.bronze_mdl_grades")
result_src = _g.join(_u, "userid").selectExpr(
    "userid AS student_moodle_id", "email", "courseid AS course_sourced_id",
    "assignid AS line_item_id", "nota", "timemodified AS scored_at")
result_dqx = dq.apply_checks_by_metadata(result_src, RESULT_CHECKS)
validos_sin_errores(result_dqx).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SILVER}.result")
solo_errores(result_dqx).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SILVER}.quarantine_result")

# --- caliper_event (Caliper) ---
_l = spark.table(f"{BRONZE}.bronze_mdl_logstore_standard_log")
_l.join(_u, "userid").selectExpr(
    "userid AS student_moodle_id", "email", "courseid AS course_sourced_id",
    "action", "target", "timecreated AS event_time"
).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SILVER}.caliper_event")

print("✓ Silver construido (canónico HERM/1EdTech) con cuarentena DQX en person y result")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.1 Ver la cuarentena en acción
# MAGIC
# MAGIC Con datos limpios, la cuarentena estará (casi) vacía — pero el **mecanismo** está activo.
# MAGIC Prueba tú: inserta una fila con `nota=99` en `bronze_mdl_grades`, re-ejecuta la celda de
# MAGIC `result` y verás la fila aparecer en `quarantine_result` (regla `nota_en_rango`).

# COMMAND ----------

v = spark.table(f"{SILVER}.person").count()
q = spark.table(f"{SILVER}.quarantine_person").count()
print(f"person → válidos: {v} · cuarentena: {q}")
r_v = spark.table(f"{SILVER}.result").count()
r_q = spark.table(f"{SILVER}.quarantine_result").count()
print(f"result → válidos: {r_v} · cuarentena: {r_q}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. GOLD — data products
# MAGIC
# MAGIC Materializamos los **productos de datos** que consumen el app, el ML y Genie. El MDM
# MAGIC (`student_360`) tiene su propio notebook (04); aquí construimos el resto. Definimos
# MAGIC `student_360` de forma mínima primero porque varios productos dependen de él (el notebook 04
# MAGIC lo profundiza y verifica).

# COMMAND ----------

# --- student_360 (MDM PeopleSoft ↔ Moodle por email + geo) — versión base ---
p  = spark.table(f"{SILVER}.person")
pr = spark.table(f"{SILVER}.program")
t  = spark.table(f"{SILVER}.academic_term")
fa = spark.table(f"{SILVER}.financial_account")
geo = spark.table(f"{BRONZE}.bronze_campus_geo").selectExpr(
    "campus_id", "ciudad", "pais_nombre", "moneda", "vertical", "lat", "lon")
mdl = spark.table(f"{SILVER}.enrollment").where("email IS NOT NULL").select("email", "student_moodle_id").dropDuplicates()

student_360 = (p.join(mdl, "email", "left").join(pr, "student_id", "left")
    .join(t, "student_id", "left").join(fa, "student_id", "left").join(geo, "campus_id", "left")
    .selectExpr("student_id AS student_master_id", "nombre", "email", "documento", "anio_nac", "genero", "pais",
        "student_moodle_id", "program_id", "program_name", "isced_f", "campus_id", "ciudad", "pais_nombre",
        "moneda", "vertical", "lat", "lon", "prog_status", "gpa", "creditos_acum", "gente_trabaja", "semestre",
        "cursos_inscritos", "dias_mora", "saldo_vencido", "mensualidad",
        "CASE WHEN student_moodle_id IS NULL THEN 'solo_SIS' ELSE 'SIS+LMS' END AS match_status"))
student_360.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.student_360")

# --- dropout_features (features de deserción + label) ---
ce = spark.table(f"{SILVER}.caliper_event").groupBy("student_moodle_id").agg(
    F.count("*").alias("eventos_lms"), F.countDistinct("course_sourced_id").alias("cursos_activos"))
no = spark.table(f"{SILVER}.result").groupBy("student_moodle_id").agg(
    F.avg("nota").alias("nota_media"), F.count("*").alias("n_notas"))
s360 = spark.table(f"{GOLD}.student_360").where("student_moodle_id IS NOT NULL")
d = s360.join(ce, "student_moodle_id", "left").join(no, "student_moodle_id", "left").fillna(0)
lbl = ((F.when(F.col("nota_media") < 11, 1).otherwise(0)
        + F.when(F.col("eventos_lms") < 15, 1).otherwise(0)
        + F.when(F.col("dias_mora") >= 30, 1).otherwise(0)) >= 2).cast("int")
d.select("student_master_id", "program_id", "campus_id", "isced_f", "gpa", "gente_trabaja",
         "dias_mora", "eventos_lms", "cursos_activos", "nota_media", "n_notas", "semestre",
         lbl.alias("desercion_label")
).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.dropout_features")

# --- campus_occupancy (ocupación + geografía) ---
agg = spark.table(f"{GOLD}.student_360").groupBy("campus_id").agg(F.count("*").alias("estudiantes"))
geo_full = spark.table(f"{BRONZE}.bronze_campus_geo")
cap = spark.table(f"{BRONZE}.bronze_campus_capacity").select("campus_id", "salas_capacidad", "alumnos_por_sala")
(agg.join(geo_full, "campus_id").join(cap, "campus_id", "left").selectExpr(
    "campus_id", "concat('Campus ', ciudad) AS campus_name", "ciudad", "pais", "pais_nombre",
    "moneda", "vertical", "lat", "lon", "mensualidad_usd", "es_sede", "estudiantes",
    "round(least(100, (estudiantes / alumnos_por_sala) / salas_capacidad * 100), 1) AS ocupacion_pct")
).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.campus_occupancy")

# --- copias directas a gold (data products de referencia) ---
for src, dst in [("bronze_campus_capacity", "campus_capacity"),
                 ("bronze_matricula_historica", "matricula_historica"),
                 ("bronze_paper_catalog", "paper_catalog")]:
    spark.table(f"{BRONZE}.{src}").write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.{dst}")

# --- admissions_funnel ---
a = spark.table(f"{BRONZE}.bronze_ps_adm_appl_data")
gcols = spark.table(f"{BRONZE}.bronze_campus_geo").select("campus_id", "ciudad", "pais_nombre")
a.join(gcols, a.campus == gcols.campus_id, "left").drop("campus_id") \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.admissions_funnel")

print("✓ Gold: student_360, dropout_features, campus_occupancy, admissions_funnel + referencias")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. GOLD — AES (redacciones) y grafo de conocimiento
# MAGIC
# MAGIC Preparamos los productos que alimentan el **AES** (notebook 09) y el **GraphRAG** (notebook 10):
# MAGIC - `essay_submissions` (enriquecidas con carrera/campus) y `essay_rubric`.
# MAGIC - `kg_nodes` / `kg_edges` — el **grafo de conocimiento** del currículo.
# MAGIC - `knowledge_chunks` — FAQs/reglamento para indexar en Vector Search.

# COMMAND ----------

# --- AES ---
e = spark.table(f"{BRONZE}.bronze_essay_submissions")
s = spark.table(f"{GOLD}.student_360").selectExpr(
    "student_master_id AS _sid", "nombre AS alumno", "program_name AS prog_nombre",
    "campus_id AS campus", "pais_nombre")
e.join(s, e.student_id == s._sid, "left").drop("_sid") \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.essay_submissions")
spark.table(f"{BRONZE}.bronze_essay_rubric").write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.essay_rubric")

# --- kg_nodes (Curso, Área ISCED-F, Programa) ---
co = spark.table(f"{SILVER}.course_offering")
s_all = spark.table(f"{GOLD}.student_360")
n_course = co.selectExpr("concat('course:', course_code) AS node_id", "'Curso' AS node_type", "course_title AS label", "course_code AS props")
n_area = s_all.where("isced_f IS NOT NULL").selectExpr("concat('area:', isced_f) AS node_id", "'Área' AS node_type", "isced_f AS label", "isced_f AS props").dropDuplicates()
n_prog = s_all.where("program_id IS NOT NULL").selectExpr("concat('program:', program_id) AS node_id", "'Programa' AS node_type", "program_name AS label", "program_id AS props").dropDuplicates()
n_course.unionByName(n_area).unionByName(n_prog) \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.kg_nodes")

# --- kg_edges (PREREQUISITE_OF, TAUGHT_IN, IN_AREA) ---
from pyspark.sql.window import Window
prereq = co.where("prereq_code IS NOT NULL").selectExpr(
    "concat('course:', prereq_code) AS src_id", "concat('course:', course_code) AS dst_id",
    "'PREREQUISITE_OF' AS rel_type", "1.0 AS weight")
enr = spark.table(f"{SILVER}.enrollment")
ti = (enr.join(co, "course_sourced_id").join(s_all.where("program_id IS NOT NULL"), "student_moodle_id")
      .groupBy("course_code", "program_id").agg(F.count("*").alias("n")))
w = Window.partitionBy("course_code").orderBy(F.col("n").desc())
taught = (ti.withColumn("rk", F.row_number().over(w)).where("rk<=2").selectExpr(
    "concat('course:', course_code) AS src_id", "concat('program:', program_id) AS dst_id",
    "'TAUGHT_IN' AS rel_type", "CAST(n AS DOUBLE) AS weight"))
in_area = s_all.where("program_id IS NOT NULL AND isced_f IS NOT NULL").selectExpr(
    "concat('program:', program_id) AS src_id", "concat('area:', isced_f) AS dst_id",
    "'IN_AREA' AS rel_type", "1.0 AS weight").dropDuplicates()
prereq.unionByName(taught).unionByName(in_area) \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.kg_edges")

# --- knowledge_chunks (FAQ/reglamento para Vector Search) ---
faqs = [
    ("faq:matricula", "¿Cómo me matriculo en un curso?", "Debes tener aprobados los prerrequisitos del curso y estar activo en tu programa."),
    ("faq:calc2", "¿Requisitos para Cálculo II?", "Debes haber aprobado Cálculo I (prerrequisito) y estar matriculado en un programa de Ingeniería."),
    ("faq:beca", "¿Cómo solicito una beca?", "Las becas socioeconómicas se solicitan con tu situación financiera y rendimiento (GPA)."),
    ("faq:mora", "¿Qué pasa si tengo mora?", "Con más de 30 días de mora se bloquea la matrícula del siguiente ciclo hasta regularizar el saldo."),
    ("faq:retiro", "¿Cómo me retiro de un curso?", "El retiro sin penalidad es posible dentro de las primeras 3 semanas del ciclo."),
    ("reglamento:4.2", "Reglamento §4.2 — Prerrequisitos", "Ningún estudiante puede inscribirse en un curso sin haber aprobado sus prerrequisitos."),
]
spark.createDataFrame(faqs, "chunk_id string, titulo string, contenido string") \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.knowledge_chunks")

print("✓ Gold: essay_submissions/rubric, kg_nodes/kg_edges, knowledge_chunks")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. La versión declarativa (SDP) — para tu referencia
# MAGIC
# MAGIC En producción, todo lo anterior es un **pipeline declarativo**. En vez de leer/escribir a
# MAGIC mano, decoras funciones que devuelven DataFrames y Databricks orquesta el DAG, el linaje y
# MAGIC la incrementalidad:
# MAGIC
# MAGIC ```python
# MAGIC import dlt
# MAGIC
# MAGIC @dlt.table(name="uts_bronze.bronze_ps_personal_data")
# MAGIC def bronze_person():
# MAGIC     return (spark.readStream.format("cloudFiles")           # ← Auto Loader (incremental)
# MAGIC             .option("cloudFiles.format", "csv").option("header", "true")
# MAGIC             .schema("emplid string, ...").load(f"{LANDING}/ps_personal_data"))
# MAGIC
# MAGIC @dlt.view(name="person_dqx")
# MAGIC def person_dqx():
# MAGIC     df = dlt.read("uts_bronze.bronze_ps_personal_data").selectExpr("emplid AS student_id", ...)
# MAGIC     return dq.apply_checks_by_metadata(df, PERSON_CHECKS)    # ← misma DQX que arriba
# MAGIC
# MAGIC @dlt.table(name="uts_silver.person")                        # Materialized View
# MAGIC def person():
# MAGIC     return validos_sin_errores(dlt.read("person_dqx"))
# MAGIC ```
# MAGIC
# MAGIC La **lógica de calidad es idéntica**; sólo cambia el motor de ejecución (batch manual aquí,
# MAGIC Streaming Tables + Materialized Views allá). Ver `src/pipeline/medallion.py` en el repo original.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Verificación

# COMMAND ----------

tablas_silver = {r.tableName for r in spark.sql(f"SHOW TABLES IN {SILVER}").collect()}
tablas_gold = {r.tableName for r in spark.sql(f"SHOW TABLES IN {GOLD}").collect()}
assert {"person", "result", "quarantine_person", "quarantine_result"} <= tablas_silver, "faltan tablas silver"
assert {"student_360", "dropout_features", "campus_occupancy", "kg_nodes", "kg_edges", "knowledge_chunks"} <= tablas_gold, "faltan tablas gold"
n360 = spark.table(f"{GOLD}.student_360").count()
print(f"✓ Silver: {len(tablas_silver)} tablas · Gold: {len(tablas_gold)} tablas")
print(f"✓ student_360: {n360} estudiantes")
print("Listo para el notebook 03 · DQX avanzado →")
display(spark.table(f"{GOLD}.campus_occupancy").select("campus_name", "pais_nombre", "estudiantes", "ocupacion_pct").orderBy(F.desc("estudiantes")))
