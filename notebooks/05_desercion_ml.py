# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Modelo de deserción (GradientBoosting + SHAP + MLflow)
# MAGIC
# MAGIC Entrenamos un modelo que predice el **riesgo de deserción** de cada alumno, con
# MAGIC **explicabilidad** (por qué está en riesgo) y lo registramos en **Unity Catalog vía MLflow**.
# MAGIC
# MAGIC | Componente | Elección | Por qué |
# MAGIC |---|---|---|
# MAGIC | Modelo | `GradientBoostingClassifier` (sklearn) | Fuerte en tabular, sin GPU, corre en serverless |
# MAGIC | Explicabilidad | **SHAP** (contribución por feature) | Justificar cada score → confianza + acción |
# MAGIC | Registro | **MLflow** + `registered_model_name` en UC | Versionado, firma, gobernanza |
# MAGIC | Scoring | Batch → tabla `dropout_scores` | El app lee la tabla, no invoca el modelo en vivo |
# MAGIC
# MAGIC Features (de `dropout_features`, notebook 02): GPA, si trabaja, morosidad, engagement LMS,
# MAGIC cursos activos, nota media, nº de evaluaciones.

# COMMAND ----------

# MAGIC %run ../_comun

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Cargar features

# COMMAND ----------

import numpy as np, pandas as pd, json, mlflow
from sklearn.ensemble import GradientBoostingClassifier
from mlflow.models.signature import infer_signature

pdf = spark.sql(f"""
    SELECT student_master_id, gpa, CAST(gente_trabaja AS INT) gente_trabaja,
           dias_mora, eventos_lms, cursos_activos, nota_media, n_notas, semestre, desercion_label
    FROM {GOLD}.dropout_features
""").toPandas()

FEATS = ["gpa", "gente_trabaja", "dias_mora", "eventos_lms", "cursos_activos", "nota_media", "n_notas"]
X, y = pdf[FEATS].fillna(0), pdf["desercion_label"].astype(int)
print(f"Dataset: {len(X)} alumnos · tasa base de deserción: {y.mean():.1%}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Entrenar y registrar en Unity Catalog (MLflow)
# MAGIC
# MAGIC Registramos en UC (`set_registry_uri("databricks-uc")`) con **firma** (`infer_signature`) para
# MAGIC que el modelo quede gobernado y versionado. Logueamos hiperparámetros, AUC y la importancia
# MAGIC global de features como artefacto del run.

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")
try:
    who = spark.sql("SELECT current_user() u").collect()[0].u
    mlflow.set_experiment(f"/Users/{who}/{PREFIX}_dropout")
except Exception:
    mlflow.set_experiment(f"/Shared/{PREFIX}_dropout")

modelo_uc = f"{ML}.dropout_model"

with mlflow.start_run(run_name="dropout_gbm") as run:
    clf = GradientBoostingClassifier(n_estimators=120, max_depth=3, learning_rate=0.1, random_state=42)
    clf.fit(X, y)
    acc = clf.score(X, y)
    mlflow.log_params({"n_features": len(FEATS), "n_estimators": 120, "max_depth": 3,
                       "learning_rate": 0.1, "n_samples": len(X)})
    mlflow.log_metric("train_accuracy", float(acc))
    mlflow.log_metric("desercion_base_rate", float(y.mean()))
    try:
        from sklearn.metrics import roc_auc_score
        mlflow.log_metric("train_auc", float(roc_auc_score(y, clf.predict_proba(X)[:, 1])))
    except Exception:
        pass
    mlflow.log_dict(dict(zip(FEATS, [float(v) for v in clf.feature_importances_])), "feature_importances.json")
    sig = infer_signature(X, clf.predict_proba(X)[:, 1])
    mlflow.sklearn.log_model(clf, "model", signature=sig, registered_model_name=modelo_uc)
    print(f"✓ Modelo registrado en UC: {modelo_uc} (train_acc={acc:.3f}) · run {run.info.run_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Scoring + explicabilidad SHAP
# MAGIC
# MAGIC Scoreamos a todos los alumnos y, para cada uno, calculamos las **contribuciones SHAP** por
# MAGIC feature (para el "waterfall" que explica su riesgo). Si SHAP no está disponible, caemos a
# MAGIC importancia global × z-score (pseudo-contribución dirigida) — no rompe.

# COMMAND ----------

proba = clf.predict_proba(X)[:, 1]
try:
    import shap
    sv = shap.TreeExplainer(clf).shap_values(X)
    sv = sv[1] if isinstance(sv, list) else sv
    contribs = np.asarray(sv); shap_ok = True
except Exception as e:
    print(f"  (SHAP no disponible, uso importancia global × z-score: {str(e)[:80]})")
    mu, sd = X.mean(), X.replace(0, np.nan).std().fillna(1)
    contribs = (((X - mu) / sd).fillna(0).values) * clf.feature_importances_; shap_ok = False

LABELS = {"gpa": "GPA bajo", "gente_trabaja": "Trabaja y estudia", "dias_mora": "Morosidad",
          "eventos_lms": "Bajo compromiso LMS", "cursos_activos": "Pocos cursos activos",
          "nota_media": "Nota media baja", "n_notas": "Pocas evaluaciones"}

def top_contribs(row):
    idx = np.argsort(-np.abs(row))[:4]
    return [{"feature": FEATS[i], "label": LABELS[FEATS[i]], "contrib": round(float(row[i]), 4)} for i in idx]

out = pdf[["student_master_id"]].copy()
out["riesgo_score"] = proba.round(4)
out["riesgo_nivel"] = pd.cut(proba, [-0.01, 0.33, 0.66, 1.01], labels=["bajo", "medio", "alto"]).astype(str)
out["factor_principal"] = [LABELS[FEATS[int(np.argmax(np.abs(contribs[k])))]] for k in range(len(out))]
out["shap_json"] = [json.dumps(top_contribs(contribs[k]), ensure_ascii=False) for k in range(len(out))]
out["shap_metodo"] = "shap" if shap_ok else "importancia_global"
# semestre en que el riesgo se concentra (heurística sobre el semestre actual): el riesgo tiende
# al 1er año y a la transición 4º→5º (cambio al ciclo especializado). El app lo usa en la ficha 360.
sem = pdf["semestre"] if "semestre" in pdf.columns else pd.Series([1] * len(out))
out["semestre_critico"] = [int(min(10, max(1, s if p > 0.5 else (2 if s <= 2 else 5)))) for s, p in zip(sem, proba)]

spark.createDataFrame(out).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{GOLD}.dropout_scores")
n_alto = (out["riesgo_nivel"] == "alto").sum()
print(f"✓ {GOLD}.dropout_scores: {len(out)} alumnos · {n_alto} en riesgo alto · método SHAP: {out['shap_metodo'].iloc[0]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Verificación

# COMMAND ----------

assert spark.table(f"{GOLD}.dropout_scores").count() == len(X)
print("Distribución de riesgo:")
display(spark.sql(f"SELECT riesgo_nivel, count(*) n FROM {GOLD}.dropout_scores GROUP BY riesgo_nivel ORDER BY n DESC"))
print("Factores de riesgo más comunes:")
display(spark.sql(f"SELECT factor_principal, count(*) n FROM {GOLD}.dropout_scores GROUP BY factor_principal ORDER BY n DESC"))
