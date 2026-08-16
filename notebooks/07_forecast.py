# Databricks notebook source
# MAGIC %md
# MAGIC # 07 · Forecast de matrícula por campus
# MAGIC
# MAGIC Proyectamos la **matrícula futura** de cada campus a partir del histórico multi-semestre
# MAGIC (`matricula_historica`). Alimenta la vista "Carrera 360" y sirve de *baseline* al **Digital
# MAGIC Twin** del campus (simulación de capacidad).
# MAGIC
# MAGIC > Databricks ofrece la función SQL nativa **`AI_FORECAST`** para series temporales. Como está
# MAGIC > en *preview* y puede no estar habilitada en tu workspace, aquí usamos una **regresión lineal
# MAGIC > cerrada en Spark SQL** (slope = cov(x,y)/var(x)) — portable, sin dependencias. Al final
# MAGIC > mostramos cómo sería con `AI_FORECAST`.

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. El histórico disponible

# COMMAND ----------

display(spark.sql(f"""
    SELECT campus_id, strm, matricula FROM {GOLD}.matricula_historica
    ORDER BY campus_id, periodo_idx LIMIT 18"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Proyección por regresión lineal (Spark SQL)
# MAGIC
# MAGIC Para cada campus calculamos la pendiente de la tendencia y proyectamos **2 semestres futuros
# MAGIC (2027-1, 2027-2)** con una banda de confianza simple (±1.5·desviación).

# COMMAND ----------

spark.sql(f"""
  CREATE OR REPLACE TABLE {GOLD}.matricula_forecast AS
  WITH coef AS (
    SELECT campus_id,
           avg(periodo_idx) AS mx, avg(matricula) AS my,
           (avg(periodo_idx * matricula) - avg(periodo_idx)*avg(matricula)) /
             nullif(avg(periodo_idx*periodo_idx) - avg(periodo_idx)*avg(periodo_idx), 0) AS slope,
           max(periodo_idx) AS maxidx, coalesce(stddev(matricula), 0) AS sd
    FROM {GOLD}.matricula_historica GROUP BY campus_id
  ),
  fut AS (
    SELECT c.campus_id,
           concat('2027-', CASE WHEN h=1 THEN '1' ELSE '2' END) AS ds,
           c.my + c.slope * ((c.maxidx + h) - c.mx) AS y, c.sd AS sd
    FROM coef c LATERAL VIEW explode(array(1,2)) t AS h
  )
  SELECT campus_id, ds, round(y) AS y, round(y - 1.5*sd) AS y_lower, round(y + 1.5*sd) AS y_upper
  FROM fut
""")
r = spark.sql(f"SELECT count(*) c, count(DISTINCT campus_id) camp FROM {GOLD}.matricula_forecast").collect()[0]
print(f"✓ {GOLD}.matricula_forecast: {r.c} filas · {r.camp} campus proyectados")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. La alternativa nativa: `AI_FORECAST`
# MAGIC
# MAGIC Si tu workspace tiene `AI_FORECAST` habilitado, el mismo resultado se obtiene con una sola
# MAGIC función (maneja estacionalidad y tendencia automáticamente). Ejemplo de referencia:
# MAGIC
# MAGIC ```sql
# MAGIC SELECT * FROM AI_FORECAST(
# MAGIC   TABLE(SELECT campus_id, to_date(concat(strm,'-01')) AS ds, matricula AS y
# MAGIC         FROM uts_gold.matricula_historica),
# MAGIC   horizon => 2, time_col => 'ds', value_col => 'y', group_col => 'campus_id')
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Verificación

# COMMAND ----------

n_camp = spark.table(f"{GOLD}.campus_occupancy").count()
n_fc = spark.table(f"{GOLD}.matricula_forecast").select("campus_id").distinct().count()
assert n_fc == n_camp, f"forecast cubre {n_fc}/{n_camp} campus"
print(f"✓ Forecast para los {n_fc} campus.")
display(spark.sql(f"""
    SELECT campus_id, ds, y AS matricula_proyectada, y_lower, y_upper
    FROM {GOLD}.matricula_forecast ORDER BY campus_id, ds"""))
