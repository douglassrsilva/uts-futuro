"""Digital Twin del campus — simulación what-if de demanda de recursos vs capacidad.

Baseline: matrícula actual + forecast (AI_FORECAST). Driver: slider de crecimiento (%).
Recursos: salas, energía, restaurante, laboratorios, dormitorios.
Es forecast + reglas de capacidad + señalización de déficit — no 3D físico.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from ..config import query, CATALOG

router = APIRouter(prefix="/api", tags=["digitaltwin"])
G = f"{CATALOG}.uts_gold"

# La demanda de recursos depende de la FASE de la carrera (debe coincidir con el gerador de
# datos, src/generate_data.py): coeficiente multiplicador sobre la demanda base por alumno.
BASE_DEM = {"salas": 1 / 35, "energia": 4.2, "restaurante": 0.62, "labs": 1 / 90, "dorms": 0.18}
PHASE_COEF = {
    "salas":       {"inicial": 1.30, "media": 1.00, "final": 0.55},
    "energia":     {"inicial": 0.90, "media": 1.00, "final": 1.20},
    "restaurante": {"inicial": 1.25, "media": 1.00, "final": 0.70},
    "labs":        {"inicial": 0.35, "media": 1.00, "final": 2.10},
    "dorms":       {"inicial": 1.40, "media": 1.00, "final": 0.65},
}
_CAP = {"salas": "salas_capacidad", "energia": "energia_kwh_capacidad", "restaurante": "comedor_capacidad",
        "labs": "labs_capacidad", "dorms": "camas_capacidad"}


def _demanda_por_fase(res, comp):
    """Demanda de un recurso = Σ (n_alumnos_fase × coef_fase) × demanda_base_por_alumno."""
    return BASE_DEM[res] * sum(comp.get(f, 0) * PHASE_COEF[res][f] for f in ("inicial", "media", "final"))


@router.get("/digitaltwin/estado")
def estado():
    """Estado actual: matrícula + capacidad + composición por fase por campus (con geo)."""
    return query(f"""
        SELECT c.campus_id, g.ciudad, g.pais_nombre, g.lat, g.lon, g.vertical,
               o.estudiantes, c.salas_capacidad, c.energia_kwh_capacidad, c.comedor_capacidad,
               c.labs_capacidad, c.camas_capacidad, c.n_inicial, c.n_media, c.n_final
        FROM {G}.campus_capacity c
        JOIN {G}.campus_occupancy o ON o.campus_id=c.campus_id
        JOIN {G}.campus_geo g ON g.campus_id=c.campus_id""") if _has(f"{G}.campus_geo") else \
        query(f"""
        SELECT c.campus_id, o.ciudad, o.pais_nombre, o.lat, o.lon, o.vertical,
               o.estudiantes, c.salas_capacidad, c.energia_kwh_capacidad, c.comedor_capacidad,
               c.labs_capacidad, c.camas_capacidad, c.n_inicial, c.n_media, c.n_final
        FROM {G}.campus_capacity c JOIN {G}.campus_occupancy o ON o.campus_id=c.campus_id""")


def _has(fq):
    try:
        query(f"SELECT 1 FROM {fq} LIMIT 1"); return True
    except Exception:
        return False


@router.get("/campus/{cid}")
def campus_detail(cid: str):
    """Ficha individual de un campus: perfil + infraestructura (demanda actual vs capacidad)."""
    rows = [c for c in estado() if c["campus_id"] == cid]  # comparación en Python, no SQL
    if not rows:
        return JSONResponse(status_code=404, content={"error": "campus no encontrado"})
    c = rows[0]
    comp = {"inicial": c.get("n_inicial", 0), "media": c.get("n_media", 0), "final": c.get("n_final", 0)}
    def rec(res, unidad, icon, label):
        dem = _demanda_por_fase(res, comp); cap = c[_CAP[res]]
        pct = round(dem / cap * 100, 0) if cap else 0
        return {"label": label, "icon": icon, "demanda": round(dem), "capacidad": cap, "uso": pct,
                "estado": "critico" if pct > 100 else "ajustado" if pct > 85 else "ok", "unidad": unidad}
    infra = [
        rec("salas", "aulas", "🏫", "Salas de aula"),
        rec("energia", "kWh/día", "⚡", "Energía"),
        rec("restaurante", "comidas/día", "🍽", "Restaurante"),
        rec("labs", "labs", "🔬", "Laboratorios"),
        rec("dorms", "camas", "🛏", "Alojamiento"),
    ]
    # alumnos en riesgo de este campus
    riesgo = query(f"""SELECT count(*) n FROM {G}.dropout_scores d JOIN {G}.student_360 s
                       ON s.student_master_id=d.student_master_id
                       WHERE s.campus_id = :cid AND d.riesgo_nivel='alto'""", {"cid": cid})
    return {"campus": c, "infra": infra, "en_riesgo": riesgo[0]["n"] if riesgo else 0}


class Sim(BaseModel):
    crecimiento_pct: float = 0.0   # ajuste manual sobre el baseline
    usar_forecast: bool = True     # partir del forecast (si existe) o de la matrícula actual


@router.post("/digitaltwin/simulate")
def simulate(req: Sim):
    campus = estado()
    factor = 1 + req.crecimiento_pct / 100.0
    # La base es SIEMPRE la matrícula ACTUAL → 0% de crecimiento = estado real (sin déficit
    # fantasma). El forecast es una proyección OPCIONAL que el usuario activa explícitamente
    # (usar_forecast) para ver el escenario tendencial además del ajuste manual del slider.
    fc = {}
    if req.usar_forecast:
        try:
            for r in query(f"""SELECT campus_id, round(max_by(y, ds)) proj FROM {G}.matricula_forecast GROUP BY campus_id"""):
                fc[r["campus_id"]] = r["proj"]
        except Exception:
            fc = {}
    out = []
    for c in campus:
        actual = c["estudiantes"]
        base = fc.get(c["campus_id"], actual) if req.usar_forecast else actual
        n = base * factor
        comp0 = {"inicial": c.get("n_inicial", 0), "media": c.get("n_media", 0), "final": c.get("n_final", 0)}
        # El crecimiento entra por la FASE INICIAL (se crece admitiendo más ingresantes): el
        # extra de matrícula se suma a 'inicial'. Así salas/comedor/dormitorios presionan primero
        # y los laboratorios sólo se saturan cuando esa cohorte llega al ciclo especializado.
        extra = n - sum(comp0.values())
        comp = dict(comp0); comp["inicial"] = comp0["inicial"] + extra
        def rec(res, unidad):
            dem = _demanda_por_fase(res, comp); cap = c[_CAP[res]]
            pct = round(dem / cap * 100, 0) if cap else 0
            estado = "critico" if pct > 100 else "ajustado" if pct > 85 else "ok"
            return {"demanda": round(dem), "capacidad": cap, "uso_pct": pct, "estado": estado, "unidad": unidad}
        out.append({
            "campus_id": c["campus_id"], "ciudad": c["ciudad"], "pais": c["pais_nombre"],
            "lat": c["lat"], "lon": c["lon"], "vertical": c["vertical"],
            "matricula_sim": round(n), "matricula_base": round(base),
            "recursos": {
                "salas": rec("salas", "aulas"),
                "energia": rec("energia", "kWh/día"),
                "restaurante": rec("restaurante", "comidas/día"),
                "laboratorios": rec("labs", "labs"),
                "dormitorios": rec("dorms", "camas"),
            }
        })
    return {"crecimiento_pct": req.crecimiento_pct, "campus": out}
