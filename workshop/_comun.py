# Databricks notebook source
# MAGIC %md
# MAGIC # ⚙️ `_comun` · Configuración compartida del workshop UTS
# MAGIC
# MAGIC Este notebook **no se ejecuta suelto**: cada notebook del workshop (en `notebooks/`) lo
# MAGIC invoca con `%run ../_comun` para heredar la **misma configuración**.
# MAGIC
# MAGIC Define tres *widgets* que **generalizan** toda la experiencia — cámbialos una vez y
# MAGIC todos los notebooks apuntan a tu espacio:
# MAGIC
# MAGIC | Widget | Qué es | Ejemplo |
# MAGIC |---|---|---|
# MAGIC | `catalog` | Tu catálogo Unity (necesitas `CREATE SCHEMA`) | `main`, `mi_catalogo` |
# MAGIC | `schema_prefix` | Prefijo de tus 5 schemas — **cámbialo si compartes catálogo** | `uts`, `uts_ana` |
# MAGIC | `warehouse_id` | ID del SQL Warehouse (Metric Views, Genie, app) | `abc123...` |
# MAGIC
# MAGIC Con `schema_prefix = uts` los schemas son `uts_bronze`, `uts_silver`, `uts_gold`,
# MAGIC `uts_ml`, `uts_ops`. Con `schema_prefix = uts_ana` serían `uts_ana_bronze`, etc. — así
# MAGIC **cada participante** trabaja aislado dentro del mismo catálogo.

# COMMAND ----------

# Widgets (idempotentes: si ya existen, conserva el valor actual)
dbutils.widgets.text("catalog", "main", "1 · Catálogo Unity")
dbutils.widgets.text("schema_prefix", "uts", "2 · Prefijo de schema")
dbutils.widgets.text("warehouse_id", "", "3 · SQL Warehouse ID (opcional)")

CATALOG = dbutils.widgets.get("catalog").strip()
PREFIX = dbutils.widgets.get("schema_prefix").strip() or "uts"
WAREHOUSE_ID = dbutils.widgets.get("warehouse_id").strip()

# --- Nombres de schema derivados del prefijo (una sola fuente de verdad) ---
BRONZE = f"{CATALOG}.{PREFIX}_bronze"
SILVER = f"{CATALOG}.{PREFIX}_silver"
GOLD   = f"{CATALOG}.{PREFIX}_gold"
ML     = f"{CATALOG}.{PREFIX}_ml"
OPS    = f"{CATALOG}.{PREFIX}_ops"

# Volúmenes clave (aterrizaje de datos y assets)
LANDING = f"/Volumes/{CATALOG}/{PREFIX}_bronze/landing"
ESSAYS  = f"/Volumes/{CATALOG}/{PREFIX}_bronze/essays"
DOCS    = f"/Volumes/{CATALOG}/{PREFIX}_gold/documentos"

SCHEMAS = {
    f"{PREFIX}_bronze": "Datos crudos de Moodle (LMS) y PeopleSoft (SIS) + eventos Caliper.",
    f"{PREFIX}_silver": "Modelo canónico HERM / 1EdTech (OneRoster + Caliper) tipado y validado con DQX.",
    f"{PREFIX}_gold":   "Data products: student_360, riesgo, ocupación, grafo de conocimiento, chunks para VS.",
    f"{PREFIX}_ml":     "Feature tables, modelos registrados, servicios de Unity AI Gateway.",
    f"{PREFIX}_ops":    "Observabilidad de calidad de datos: DQX (ODCS, PII, anomalías, PK), reportes.",
}

# COMMAND ----------

def crear_schemas():
    """Crea (idempotente) los 5 schemas del workshop en tu catálogo. Aditivo: nunca borra."""
    for nombre, comentario in SCHEMAS.items():
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{nombre} COMMENT '{comentario}'")
    print(f"✓ Schemas listos en {CATALOG}: {', '.join(SCHEMAS)}")


def crear_volumenes():
    """Crea (idempotente) los volúmenes de aterrizaje/assets."""
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {BRONZE}.landing")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {BRONZE}.essays")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {GOLD}.documentos")
    print(f"✓ Volúmenes listos: landing, essays (bronze) · documentos (gold)")


def resumen_config():
    print("──────────────────────────────────────────────")
    print(f"  Catálogo   : {CATALOG}")
    print(f"  Prefijo    : {PREFIX}")
    print(f"  Warehouse  : {WAREHOUSE_ID or '(no configurado)'}")
    print("  Schemas    :")
    for s in SCHEMAS:
        print(f"    · {CATALOG}.{s}")
    print(f"  Landing    : {LANDING}")
    print("──────────────────────────────────────────────")


print(f"✓ _comun cargado · CATALOG={CATALOG} · PREFIX={PREFIX}")
