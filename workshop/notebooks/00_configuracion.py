# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Configuración del workshop UTS
# MAGIC
# MAGIC **Universidad Tecnológica de Sudamérica** — plataforma de datos e IA end-to-end.
# MAGIC
# MAGIC Este primer notebook prepara tu espacio de trabajo:
# MAGIC 1. Define los **widgets** (catálogo, prefijo de schema, warehouse) que **todos** los
# MAGIC    notebooks heredan.
# MAGIC 2. Crea los **5 schemas** y los **volúmenes** que usaremos.
# MAGIC 3. Verifica que todo quedó en su sitio.
# MAGIC
# MAGIC > 💡 **Aislamiento entre participantes.** Si compartes catálogo con otras personas, cambia
# MAGIC > el widget `schema_prefix` a algo único (p. ej. `uts_ana`). Todas tus tablas quedarán
# MAGIC > namespaced (`uts_ana_bronze`, `uts_ana_silver`, …) y no habrá colisiones. Lo ideal es
# MAGIC > que cada quien use **su propio catálogo**.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Cargar la configuración compartida
# MAGIC
# MAGIC Todo el workshop lee su configuración de `_comun` (en la raíz de `workshop/`). Al invocarlo
# MAGIC con `%run`, sus variables (`CATALOG`, `BRONZE`, `SILVER`, …) quedan disponibles aquí.
# MAGIC
# MAGIC **Antes de ejecutar**, ajusta los widgets que aparecerán arriba (Catálogo / Prefijo / Warehouse).

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

resumen_config()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Crear schemas y volúmenes (idempotente)
# MAGIC
# MAGIC | Schema | Contenido |
# MAGIC |---|---|
# MAGIC | `*_bronze` | Datos crudos de Moodle + PeopleSoft (Streaming Tables) |
# MAGIC | `*_silver` | Modelo canónico HERM / 1EdTech, tipado y validado con DQX |
# MAGIC | `*_gold` | Data products: `student_360`, riesgo, ocupación, grafo, chunks |
# MAGIC | `*_ml` | Feature tables, modelos registrados, servicios del AI Gateway |
# MAGIC | `*_ops` | Observabilidad de calidad de datos (reportes DQX) |
# MAGIC
# MAGIC Volúmenes: `landing` (aterrizaje de CSV), `essays` (redacciones AES), `documentos` (papers).
# MAGIC
# MAGIC Todo con `CREATE ... IF NOT EXISTS` → **puedes re-ejecutar sin miedo**.

# COMMAND ----------

crear_schemas()
crear_volumenes()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Verificación
# MAGIC
# MAGIC Confirmamos que los 5 schemas existen en tu catálogo.

# COMMAND ----------

existentes = {r.databaseName for r in spark.sql(f"SHOW SCHEMAS IN {CATALOG}").collect()}
faltan = [s for s in SCHEMAS if s not in existentes]
assert not faltan, f"Faltan schemas: {faltan}"
print(f"✓ Los {len(SCHEMAS)} schemas del workshop están creados en {CATALOG}.")
print("\nListos para el notebook 01 · Generación de datos →")
display(spark.sql(f"SHOW SCHEMAS IN {CATALOG}").filter(f"databaseName LIKE '{PREFIX}\\_%'"))
