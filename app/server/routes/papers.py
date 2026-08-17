"""Papers académicos — catálogo, búsqueda relacionada y visor de PDF inline."""
from fastapi import APIRouter
from fastapi.responses import Response, StreamingResponse
from ..config import query, read_volume_file, CATALOG

router = APIRouter(prefix="/api", tags=["papers"])
G = f"{CATALOG}.uts_gold"


@router.get("/papers")
def papers(q: str = "", isced: str = ""):
    """Lista/busca papers por título, abstract o área. Búsqueda parametrizada:
    los comodines LIKE se escapan y el patrón se pasa como parámetro (inmune a inyección
    y a metacaracteres LIKE como % o _ inyectados por el usuario)."""
    where, params = [], {}
    if q:
        # término como parámetro (inmune a inyección); neutralizamos comodines LIKE del usuario
        # sustituyéndolos (sólo afectan al alcance de la búsqueda, no a la seguridad).
        pat = "%" + q.lower().replace("%", " ").replace("_", " ") + "%"
        where.append("(lower(titulo) LIKE :p1 OR lower(abstract) LIKE :p2)")
        params["p1"] = pat; params["p2"] = pat
    if isced:
        where.append("isced_f = :isced"); params["isced"] = isced
    w = ("WHERE " + " AND ".join(where)) if where else ""
    return query(f"""SELECT paper_id, titulo, autores, anio, isced_f, abstract, pdf_path, citas
                     FROM {G}.paper_catalog {w} ORDER BY citas DESC LIMIT 40""", params)


@router.get("/papers/{paper_id}/pdf")
def paper_pdf(paper_id: str):
    """Sirve el PDF del paper desde el Volumen governado (Unity Catalog), inline."""
    rows = query(f"SELECT pdf_path FROM {G}.paper_catalog WHERE paper_id = :pid LIMIT 1",
                 {"pid": paper_id})
    if not rows:
        return Response(status_code=404, content=b"paper no encontrado")
    pid = paper_id.replace('"', "")  # sólo para el header Content-Disposition (no SQL)
    rel = rows[0]["pdf_path"]  # ej. documentos/paper_003.pdf
    vol_path = f"/Volumes/{CATALOG}/uts_gold/{rel}"
    try:
        data = read_volume_file(vol_path)  # Files API primero, fallback POSIX
    except Exception as e:
        return Response(status_code=500, content=f"no se pudo leer el PDF: {str(e)[:120]}".encode())
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{pid}.pdf"'})
