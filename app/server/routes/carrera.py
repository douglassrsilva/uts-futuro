"""Carrera 360 — crecimiento, forecast, funil de progresión por semestre, abandono por semestre."""
from fastapi import APIRouter
from ..config import query, CATALOG

router = APIRouter(prefix="/api", tags=["carrera"])
G = f"{CATALOG}.uts_gold"


@router.get("/carrera/programas")
def programas():
    """Matrícula por programa + tasa de riesgo (para ranking de crecimiento/salud)."""
    return query(f"""
        SELECT s.program_id, s.program_name, s.isced_f, count(*) alumnos,
               round(avg(s.gpa),1) gpa_medio,
               round(avg(CASE WHEN d.riesgo_nivel='alto' THEN 1 ELSE 0 END),3) tasa_riesgo
        FROM {G}.student_360 s
        LEFT JOIN {G}.dropout_scores d ON d.student_master_id=s.student_master_id
        WHERE s.program_id IS NOT NULL
        GROUP BY s.program_id, s.program_name, s.isced_f
        ORDER BY alumnos DESC""")


@router.get("/carrera/funil_semestre")
def funil_semestre(programa: str = ""):
    """Progresión: cuántos alumnos hay en cada semestre (embudo de avance)."""
    w, params = "", {}
    if programa:
        w = "AND program_id = :prog"; params["prog"] = programa
    return query(f"""SELECT semestre, count(*) alumnos FROM {G}.student_360
                     WHERE semestre IS NOT NULL {w} GROUP BY semestre ORDER BY semestre""", params)


@router.get("/carrera/abandono_semestre")
def abandono_semestre(programa: str = ""):
    """En qué semestre se concentra la propensión de abandono (curva de riesgo por semestre)."""
    w, params = "", {}
    if programa:
        w = "AND s.program_id = :prog"; params["prog"] = programa
    return query(f"""
        SELECT d.semestre_critico AS semestre, count(*) en_riesgo
        FROM {G}.dropout_scores d JOIN {G}.student_360 s ON s.student_master_id=d.student_master_id
        WHERE d.riesgo_nivel IN ('alto','medio') {w}
        GROUP BY d.semestre_critico ORDER BY semestre""", params)


@router.get("/carrera/forecast")
def forecast():
    """Forecast de matrícula por campus (AI_FORECAST)."""
    try:
        return query(f"""SELECT campus_id, ds, round(y) matricula, round(y_lower) lo, round(y_upper) hi
                         FROM {G}.matricula_forecast ORDER BY campus_id, ds""")
    except Exception:
        return []
