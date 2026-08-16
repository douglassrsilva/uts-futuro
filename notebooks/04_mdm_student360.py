# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · MDM — reconciliar el alumno entre SIS y LMS (`student_360`)
# MAGIC
# MAGIC El **mismo estudiante** existe en dos sistemas con **identificadores distintos**:
# MAGIC
# MAGIC - En **PeopleSoft (SIS)** es `emplid` (p. ej. `S000123`).
# MAGIC - En **Moodle (LMS)** es `userid` (p. ej. `10123`).
# MAGIC
# MAGIC **Master Data Management (MDM):** necesitamos un **identificador maestro único**
# MAGIC (`student_master_id`) que una ambos mundos. El **puente** es el **email institucional**
# MAGIC (un patrón eMPI-like — *enterprise master patient/person index*).
# MAGIC
# MAGIC El notebook 02 ya construyó una versión base de `student_360`; aquí lo hacemos **explícito y
# MAGIC didáctico**: mostramos la lógica de matching, medimos la calidad de la reconciliación y
# MAGIC dejamos la tabla verificada.

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

from pyspark.sql import functions as F

# MAGIC %md
# MAGIC ## 1. El problema: dos identidades del mismo alumno

# COMMAND ----------

print("PeopleSoft (person) — identidad SIS:")
display(spark.table(f"{SILVER}.person").select("student_id", "nombre", "email").limit(3))

print("Moodle (enrollment) — identidad LMS:")
display(spark.table(f"{SILVER}.enrollment").select("student_moodle_id", "email").distinct().limit(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. La resolución de entidad — matching por email
# MAGIC
# MAGIC Unimos `person` (SIS) con las matrículas de Moodle (LMS) por **email normalizado**. El
# MAGIC resultado es el `student_master_id` (= `student_id` del SIS, que tomamos como maestro).
# MAGIC
# MAGIC Marcamos el `match_status`:
# MAGIC - `SIS+LMS` — el alumno se encontró en **ambos** sistemas (reconciliado).
# MAGIC - `solo_SIS` — está en el SIS pero no matriculado en Moodle (aún no cursa / caso a revisar).

# COMMAND ----------

# puente LMS: email → student_moodle_id (deduplicado)
mdl = (spark.table(f"{SILVER}.enrollment")
       .where("email IS NOT NULL")
       .select(F.lower(F.trim("email")).alias("email"), "student_moodle_id")
       .dropDuplicates())

person = spark.table(f"{SILVER}.person").withColumn("email_norm", F.lower(F.trim("email")))
recon = person.join(mdl, person.email_norm == mdl.email, "left")

resumen = recon.groupBy(
    F.when(F.col("student_moodle_id").isNull(), "solo_SIS").otherwise("SIS+LMS").alias("match_status")
).count()
print("Calidad de la reconciliación:")
display(resumen)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Ensamblar `student_360` — la vista 360° del alumno
# MAGIC
# MAGIC Enriquecemos la identidad reconciliada con **programa** (ISCED-F), **término académico**
# MAGIC (GPA, semestre, si trabaja), **finanzas** (mora, saldo) y **geografía del campus**. Es el
# MAGIC data product central que consumen el app, el ML y Genie.

# COMMAND ----------

p  = spark.table(f"{SILVER}.person")
pr = spark.table(f"{SILVER}.program")
t  = spark.table(f"{SILVER}.academic_term")
fa = spark.table(f"{SILVER}.financial_account")
geo = spark.table(f"{BRONZE}.bronze_campus_geo").selectExpr(
    "campus_id", "ciudad", "pais_nombre", "moneda", "vertical", "lat", "lon")
mdl_bridge = (spark.table(f"{SILVER}.enrollment").where("email IS NOT NULL")
              .select("email", "student_moodle_id").dropDuplicates())

student_360 = (p.join(mdl_bridge, "email", "left").join(pr, "student_id", "left")
    .join(t, "student_id", "left").join(fa, "student_id", "left").join(geo, "campus_id", "left")
    .selectExpr("student_id AS student_master_id", "nombre", "email", "documento", "anio_nac", "genero", "pais",
        "student_moodle_id", "program_id", "program_name", "isced_f", "campus_id", "ciudad", "pais_nombre",
        "moneda", "vertical", "lat", "lon", "prog_status", "gpa", "creditos_acum", "gente_trabaja", "semestre",
        "cursos_inscritos", "dias_mora", "saldo_vencido", "mensualidad",
        "CASE WHEN student_moodle_id IS NULL THEN 'solo_SIS' ELSE 'SIS+LMS' END AS match_status"))

student_360.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.student_360")
print(f"✓ {GOLD}.student_360 reconstruido")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Verificación — unicidad del identificador maestro
# MAGIC
# MAGIC La regla de oro del MDM: **un alumno, un `student_master_id`** (sin fan-out por el join).

# COMMAND ----------

total = spark.table(f"{GOLD}.student_360").count()
distintos = spark.table(f"{GOLD}.student_360").select("student_master_id").distinct().count()
print(f"student_360: {total} filas · {distintos} identificadores maestros distintos")
assert total == distintos, f"¡Fan-out! {total} filas vs {distintos} distintos — revisa los joins (deduplicación del puente LMS)."
pct_lms = spark.table(f"{GOLD}.student_360").where("match_status = 'SIS+LMS'").count() / total * 100
print(f"✓ Sin fan-out: 1 fila por alumno. {pct_lms:.1f}% reconciliados con LMS.")
display(spark.table(f"{GOLD}.student_360").select(
    "student_master_id", "nombre", "email", "student_moodle_id", "program_name", "campus_id", "gpa", "match_status").limit(8))
