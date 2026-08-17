# Databricks notebook source
# MAGIC %md
# MAGIC # 08 · Metric Views — la capa semántica gobernada
# MAGIC
# MAGIC Una **Metric View** define **dimensiones** y **measures** con nombres de negocio, de modo que
# MAGIC el app, Genie y AI/BI consulten **una sola definición** de cada métrica ("tasa de deserción",
# MAGIC "ocupación", "GPA promedio"). Se consulta con `SELECT dim, MEASURE(medida) ... GROUP BY dim`.
# MAGIC
# MAGIC Ventaja: la lógica de la métrica vive **una vez**, gobernada; nadie la reimplementa (ni la
# MAGIC calcula distinto) en cada dashboard o consulta.
# MAGIC
# MAGIC Sintaxis: `CREATE VIEW ... WITH METRICS LANGUAGE YAML AS $$ ... $$`.

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Definir las Metric Views (YAML)
# MAGIC
# MAGIC Tres vistas semánticas sobre el Gold: estudiantes, deserción y ocupación.

# COMMAND ----------

VIEWS = {
    "mv_estudiantes": f"""version: 0.1
source: {GOLD}.student_360
dimensions:
  - name: Campus
    expr: campus_id
  - name: Programa
    expr: program_name
  - name: Area
    expr: isced_f
  - name: Pais
    expr: pais
  - name: Estado matricula
    expr: prog_status
  - name: Trabaja y estudia
    expr: gente_trabaja
measures:
  - name: Alumnos
    expr: count(1)
  - name: GPA promedio
    expr: avg(gpa)
  - name: Dias mora promedio
    expr: avg(dias_mora)
  - name: Saldo vencido total
    expr: sum(saldo_vencido)
""",
    "mv_desercion": f"""version: 0.1
source: {GOLD}.dropout_features
dimensions:
  - name: Campus
    expr: campus_id
  - name: Programa
    expr: program_id
  - name: Area
    expr: isced_f
measures:
  - name: Alumnos evaluados
    expr: count(1)
  - name: En riesgo
    expr: sum(desercion_label)
  - name: Tasa de desercion
    expr: avg(desercion_label)
  - name: Engagement LMS promedio
    expr: avg(eventos_lms)
  - name: Nota media
    expr: avg(nota_media)
""",
    "mv_ocupacion": f"""version: 0.1
source: {GOLD}.campus_occupancy
dimensions:
  - name: Campus
    expr: campus_name
measures:
  - name: Estudiantes
    expr: sum(estudiantes)
  - name: Ocupacion promedio
    expr: avg(ocupacion_pct)
""",
}

for name, yaml in VIEWS.items():
    fq = f"{GOLD}.{name}"
    spark.sql(f"CREATE OR REPLACE VIEW {fq} WITH METRICS LANGUAGE YAML AS $${yaml}$$")
    print(f"✓ Metric View creada: {fq}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Consultar con `MEASURE()`
# MAGIC
# MAGIC Nota la sintaxis: se agrupa por la **dimensión** (nombre de negocio) y se envuelve la
# MAGIC **measure** en `MEASURE(...)`. El motor resuelve la agregación correcta.

# COMMAND ----------

print("Tasa de deserción por campus:")
display(spark.sql(f"""
    SELECT Campus, round(MEASURE(`Tasa de desercion`), 3) AS tasa, MEASURE(`Alumnos evaluados`) AS n
    FROM {GOLD}.mv_desercion GROUP BY Campus ORDER BY tasa DESC"""))

# COMMAND ----------

print("GPA promedio y morosidad por programa:")
display(spark.sql(f"""
    SELECT Programa, round(MEASURE(`GPA promedio`), 2) AS gpa, round(MEASURE(`Dias mora promedio`), 1) AS mora
    FROM {GOLD}.mv_estudiantes GROUP BY Programa ORDER BY gpa DESC"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Verificación

# COMMAND ----------

for name in VIEWS:
    tipo = spark.sql(f"DESCRIBE EXTENDED {GOLD}.{name}")
    print(f"✓ {GOLD}.{name} existe")
print("\nMetric Views listas — Genie y el app las usarán como fuente única de métricas.")
