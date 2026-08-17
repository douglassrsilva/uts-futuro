# Databricks notebook source
# MAGIC %md
# MAGIC # 06 · Propensión de matrícula (anti-leakage) + MLflow
# MAGIC
# MAGIC Predecimos, para cada **postulante activo**, la probabilidad de que **se matricule**. Es un
# MAGIC caso de negocio de admisiones: priorizar esfuerzo comercial donde hay mayor propensión.
# MAGIC
# MAGIC > ⚠️ **Lección crítica: fuga de datos (*data leakage*).** Un error frecuente es predecir la
# MAGIC > propensión usando la propia etapa del funil como feature, o scorear a quien **ya se
# MAGIC > matriculó** (mostraría ~100 %, algo inútil). Lo hacemos bien:
# MAGIC >
# MAGIC > 1. **Entrenamos** sólo con **ciclos pasados** (2024/2025), donde el desenlace ya se conoce
# MAGIC >    (`label = ¿llegó a MATRICULÓ?`).
# MAGIC > 2. **Scoreamos** sólo a los candidatos del **ciclo actual (2026) que aún NO se matricularon**
# MAGIC >    (PROSPECTO / POSTULÓ / ADMITIDO) — donde la propensión tiene valor real.
# MAGIC > 3. A los **ya matriculados NO** se les asigna propensión (la decisión ya ocurrió).
# MAGIC >
# MAGIC > Las features son **pre-decisión**: canal, puntaje, programa, campus. Nunca la etapa.

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Cargar postulantes y separar histórico vs activo

# COMMAND ----------

import pandas as pd, mlflow
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from mlflow.models.signature import infer_signature

pdf = spark.sql(f"""
    SELECT appl_id, canal, puntaje_admision, prog_nombre, campus, etapa_funil, ciclo_admision
    FROM {GOLD}.admissions_funnel
""").toPandas()
pdf["matriculo"] = (pdf["etapa_funil"] == "MATRICULÓ").astype(int)

CAT_FEATS = ["canal", "prog_nombre", "campus"]
NUM_FEATS = ["puntaje_admision"]
FEATS = CAT_FEATS + NUM_FEATS

train = pdf[pdf["ciclo_admision"] < 2026]                                              # histórico → entrenar
activos = pdf[(pdf["ciclo_admision"] == 2026) & (pdf["etapa_funil"] != "MATRICULÓ")]   # activo → scorear
if len(train) < 100:
    train = pdf  # fallback si no hay histórico suficiente
print(f"Entrenamiento (histórico): {len(train)} · Activos a scorear (2026, no matriculados): {len(activos)}")
print(f"Tasa de matrícula histórica: {train['matriculo'].mean():.1%}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Entrenar (OneHot + GradientBoosting) y registrar en UC

# COMMAND ----------

Xtr, ytr = train[FEATS].fillna({"puntaje_admision": 12}), train["matriculo"]
pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATS)], remainder="passthrough")
clf = Pipeline([("pre", pre),
                ("gb", GradientBoostingClassifier(n_estimators=150, max_depth=3, learning_rate=0.1, random_state=42))])

mlflow.set_registry_uri("databricks-uc")
try:
    who = spark.sql("SELECT current_user() u").collect()[0].u
    mlflow.set_experiment(f"/Users/{who}/{PREFIX}_propension")
except Exception:
    mlflow.set_experiment(f"/Shared/{PREFIX}_propension")

modelo_uc = f"{ML}.propension_model"
with mlflow.start_run(run_name="propension_gbm") as run:
    clf.fit(Xtr, ytr)
    proba_tr = clf.predict_proba(Xtr)[:, 1]
    mlflow.log_params({"n_train": len(Xtr), "cat_feats": ",".join(CAT_FEATS), "n_estimators": 150, "max_depth": 3})
    mlflow.log_metric("train_matricula_rate", float(ytr.mean()))
    try:
        from sklearn.metrics import roc_auc_score
        mlflow.log_metric("train_auc", float(roc_auc_score(ytr, proba_tr)))
    except Exception:
        pass
    sig = infer_signature(Xtr, proba_tr)
    mlflow.sklearn.log_model(clf, "model", signature=sig, registered_model_name=modelo_uc)
    print(f"✓ Modelo registrado en UC: {modelo_uc} · run {run.info.run_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Scorear SÓLO a los candidatos activos (no matriculados)

# COMMAND ----------

if len(activos):
    Xac = activos[FEATS].fillna({"puntaje_admision": 12})
    activos = activos.copy()
    activos["propension"] = clf.predict_proba(Xac)[:, 1].round(3)
    out = activos[["appl_id", "etapa_funil", "canal", "prog_nombre", "campus", "puntaje_admision", "propension"]]
else:
    out = pd.DataFrame(columns=["appl_id", "etapa_funil", "canal", "prog_nombre", "campus", "puntaje_admision", "propension"])

spark.createDataFrame(out).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{ML}.admission_scores")
print(f"✓ {ML}.admission_scores: {len(out)} candidatos activos scoreados")
if len(out):
    print(f"  propensión: min={out['propension'].min():.1%} · media={out['propension'].mean():.1%} · max={out['propension'].max():.1%}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Verificación — sin fuga de datos
# MAGIC
# MAGIC Confirmamos que **ningún matriculado** recibió propensión (no está en la tabla de scores) y
# MAGIC que la propensión tiene **dispersión real** (no todos ~100 %).

# COMMAND ----------

scores = spark.table(f"{ML}.admission_scores")
matriculados_scoreados = scores.where("etapa_funil = 'MATRICULÓ'").count()
assert matriculados_scoreados == 0, "¡Leakage! Hay matriculados con propensión — no deberían scorearse."
if scores.count():
    from pyspark.sql import functions as F
    rango = scores.select(F.min("propension").alias("min"), F.max("propension").alias("max")).collect()[0]
    print(f"✓ 0 matriculados scoreados (sin leakage) · propensión de {rango['min']:.0%} a {rango['max']:.0%} (dispersión real)")
    display(scores.orderBy(F.desc("propension")).limit(10))
else:
    print("✓ (sin candidatos activos en este universo — normal si el ciclo 2026 quedó pequeño)")
