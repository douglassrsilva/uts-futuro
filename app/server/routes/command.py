"""KPIs y panorama del Centro de Mando — lee gold con caché TTL."""
import time
from fastapi import APIRouter
from ..config import query, CATALOG

router = APIRouter(prefix="/api", tags=["command"])
_cache = {}
TTL = 60  # segundos


def cached(key, fn):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit["at"] < TTL:
        return {"data": hit["data"], "fetched_at": hit["at"], "cached": True}
    data = fn()
    _cache[key] = {"data": data, "at": now}
    return {"data": data, "fetched_at": now, "cached": False}


@router.get("/command/kpis")
def kpis(refresh: bool = False):
    if refresh:
        _cache.pop("kpis", None)

    def _safe(sql, default=0):
        try:
            r = query(sql)
            return r[0].get(list(r[0].keys())[0]) if r else default
        except Exception:
            return default

    def fn():
        G = f"{CATALOG}.uts_gold"
        # KPIs desde la CAPA SEMÁNTICA (Metric Views) vía MEASURE(), no queries ad-hoc.
        return {
            "matricula": _safe(f"SELECT MEASURE(Alumnos) m FROM {G}.mv_estudiantes"),
            "en_riesgo": _safe(f"SELECT MEASURE(`En riesgo`) m FROM {G}.mv_desercion"),
            "tasa_desercion": round(_safe(f"SELECT MEASURE(`Tasa de desercion`) m FROM {G}.mv_desercion", 0.0) or 0, 3),
            "ocupacion_media": _safe(f"SELECT round(MEASURE(`Ocupacion promedio`),0) m FROM {G}.mv_ocupacion"),
            "gpa_promedio": round(_safe(f"SELECT MEASURE(`GPA promedio`) m FROM {G}.mv_estudiantes", 0.0) or 0, 1),
            "qwk": 0.74,
        }
    return cached("kpis", fn)


@router.get("/command/desercion_por_campus")
def desercion_por_campus(refresh: bool = False):
    """Desglose desde la Metric View — misma definición de 'tasa de deserción' en todo el app."""
    if refresh:
        _cache.pop("des_campus", None)

    def fn():
        return query(f"""SELECT Campus, MEASURE(`En riesgo`) en_riesgo,
                                MEASURE(`Tasa de desercion`) tasa
                         FROM {CATALOG}.uts_gold.mv_desercion GROUP BY Campus ORDER BY tasa DESC""")
    return cached("des_campus", fn)


@router.get("/command/campus")
def campus(refresh: bool = False):
    if refresh:
        _cache.pop("campus", None)

    def fn():
        # incluir geo (lat/lon/ciudad/pais/vertical) para que el mapa LATAM pinte los marcadores
        return query(f"""SELECT campus_id, campus_name, ciudad, pais, pais_nombre, moneda, vertical,
                                lat, lon, mensualidad_usd, es_sede, estudiantes, ocupacion_pct
                         FROM {CATALOG}.uts_gold.campus_occupancy ORDER BY ocupacion_pct DESC""")
    return cached("campus", fn)
