"""Visión 360 del alumno — perfil unificado + trayectoria + riesgo (SHAP) + acción.

Seguridad: todo valor controlado por el usuario (sid, campus, nivel, limit) va como
parámetro enlazado (`:nombre`), nunca interpolado en el SQL. Identificadores de
catálogo/schema provienen de config.
"""
import json
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ..config import query, CATALOG

router = APIRouter(prefix="/api", tags=["student360"])
G = f"{CATALOG}.uts_gold"


@router.get("/student/{sid}")
def student(sid: str):
    base = query(f"SELECT * FROM {G}.student_360 WHERE student_master_id = :sid LIMIT 1",
                 {"sid": sid})
    if not base:
        return JSONResponse(status_code=404, content={"error": "no encontrado"})
    s = base[0]
    riesgo = query(f"""SELECT riesgo_score, riesgo_nivel, factor_principal, shap_json, semestre_critico
                       FROM {G}.dropout_scores WHERE student_master_id = :sid LIMIT 1""", {"sid": sid})
    r = riesgo[0] if riesgo else {}
    if r.get("shap_json"):
        try: r["shap"] = json.loads(r.pop("shap_json"))
        except Exception: r["shap"] = []
    # notas por curso (student_moodle_id es numérico → parámetro entero)
    mid = s.get("student_moodle_id")
    notas = query(f"""SELECT co.course_title, round(avg(rs.nota),1) nota, count(*) evals
                      FROM {CATALOG}.uts_silver.result rs
                      JOIN {CATALOG}.uts_silver.course_offering co ON co.course_sourced_id=rs.course_sourced_id
                      WHERE rs.student_moodle_id = :mid
                      GROUP BY co.course_title ORDER BY nota ASC LIMIT 8""", {"mid": int(mid)}) if mid else []
    # trayectoria (últimos eventos)
    tray = query(f"""SELECT tipo, detalle, ts FROM {G}.student_journey
                     WHERE student_master_id = :sid ORDER BY ts DESC LIMIT 12""", {"sid": sid})
    # acción recomendada
    accion = "Sin acción — perfil estable."
    if r.get("riesgo_nivel") == "alto":
        f = (r.get("factor_principal") or "").lower()
        if "moros" in f: accion = "Contactar a bienestar financiero: ofrecer plan de pago / beca."
        elif "compromiso" in f or "lms" in f: accion = "Tutoría proactiva: bajo compromiso en el LMS este ciclo."
        elif "nota" in f or "gpa" in f: accion = "Derivar a nivelación académica en cursos de menor nota."
        else: accion = "Revisión con consejero académico."
    return {"perfil": s, "riesgo": r, "notas": notas, "trayectoria": tray, "accion_recomendada": accion}


@router.get("/dropout/list")
def lista(nivel: str = "alto", campus: str = "", limit: int = 60):
    where, params = [], {}
    if nivel in ("alto", "medio", "bajo"):
        where.append("d.riesgo_nivel = :nivel"); params["nivel"] = nivel
    if campus:
        where.append("s.campus_id = :campus"); params["campus"] = campus
    w = ("WHERE " + " AND ".join(where)) if where else ""
    lim = max(1, min(int(limit), 500))  # limit es int (FastAPI) + acotado; no interpolamos texto libre
    return query(f"""
        SELECT d.student_master_id, s.nombre, s.program_name, s.campus_id, s.ciudad, s.pais_nombre,
               d.riesgo_score, d.riesgo_nivel, d.factor_principal, d.semestre_critico,
               s.gpa, s.dias_mora, s.gente_trabaja, s.semestre
        FROM {G}.dropout_scores d
        JOIN {G}.student_360 s ON s.student_master_id = d.student_master_id
        {w}
        ORDER BY d.riesgo_score DESC LIMIT {lim}""", params)
