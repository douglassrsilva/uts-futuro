"""Calidad de datos — observabilidad DQX (schema uts_ops).

Expone los reportes generados por src/quality/dq_advanced.py:
  · cuarentena del pipeline (get_valid/get_invalid)
  · reglas generadas desde contratos ODCS
  · PII detection + validación de formato + unicidad
  · anomaly detection (filas atípicas)
  · AI-assisted primary key detection
"""
from fastapi import APIRouter
from ..config import query, CATALOG

router = APIRouter(prefix="/api/calidad", tags=["calidad"])
OPS = f"{CATALOG}.uts_ops"


def _safe(sql_text, params=None, default=None):
    try:
        return query(sql_text, params)
    except Exception:
        return default if default is not None else []


@router.get("/resumen")
def resumen():
    """Panorama de calidad: cuarentena (gating del pipeline), reglas de contrato + PII
    aplicadas en silver, anomalías y PK detection (discovery)."""
    quarantine = _safe(f"SELECT tabla, validos, cuarentena, tasa_cuarentena_pct FROM {OPS}.dq_quarantine_summary ORDER BY tabla")
    anomaly = _safe(f"SELECT modelo, dataset, filas_total, filas_anomalas, umbral_pct FROM {OPS}.dq_anomaly_report ORDER BY modelo")
    pk = _safe(f"SELECT tabla, primary_key, confianza, razonamiento FROM {OPS}.dq_pk_detection ORDER BY tabla")
    reglas = _safe(f"SELECT contrato, regla, criticidad, funcion, argumentos FROM {OPS}.dq_contract_rules ORDER BY contrato, regla")
    contracts = _safe(f"SELECT contrato, count(*) AS reglas FROM {OPS}.dq_contract_rules GROUP BY contrato ORDER BY contrato")

    # PII: las reglas does_not_contain_pii que el pipeline aplica en silver
    pii = [{"check": r.get("regla"), "funcion": r.get("funcion"), "criticidad": r.get("criticidad"),
            "argumentos": r.get("argumentos")}
           for r in reglas if r.get("funcion") == "does_not_contain_pii"]

    # KPIs agregados
    total_cuar = sum((r.get("cuarentena") or 0) for r in quarantine if (r.get("cuarentena") or 0) >= 0)
    total_val = sum((r.get("validos") or 0) for r in quarantine if (r.get("validos") or 0) >= 0)
    tasa_global = round(total_cuar / (total_val + total_cuar) * 100, 2) if (total_val + total_cuar) > 0 else 0.0
    anom_total = sum((r.get("filas_anomalas") or 0) for r in anomaly if (r.get("filas_anomalas") or 0) >= 0)

    return {
        "kpis": {
            "tasa_cuarentena_global": tasa_global,
            "columnas_con_pii": len(pii),
            "filas_anomalas": anom_total,
            "reglas_desde_contratos": len(reglas),
        },
        "cuarentena": quarantine,
        "pii": pii,
        "anomaly": anomaly,
        "primary_keys": pk,
        "contratos": contracts,
    }


@router.get("/reglas_contrato")
def reglas_contrato(contrato: str = ""):
    """Reglas de calidad generadas automáticamente desde los contratos ODCS."""
    if contrato:
        return _safe(f"SELECT contrato, regla, criticidad, funcion, argumentos FROM {OPS}.dq_contract_rules "
                     f"WHERE contrato = :c ORDER BY contrato, regla", {"c": contrato})
    return _safe(f"SELECT contrato, regla, criticidad, funcion, argumentos FROM {OPS}.dq_contract_rules "
                 f"ORDER BY contrato, regla")
