"""Universidad Tecnológica de Sudamérica — FastAPI (backend + SPA React)."""
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.routes import command, graphrag, genie, student360, carrera, admisiones, digitaltwin, agente, papers, aes, calidad

app = FastAPI(title="Universidad Tecnológica de Sudamérica · Plataforma de Datos e IA")
app.include_router(agente.router)      # copiloto agéntico (tool-calling) — corazón del app
app.include_router(command.router)
app.include_router(graphrag.router)
app.include_router(genie.router)
app.include_router(student360.router)   # incluye /api/student/{id} y /api/dropout/list
app.include_router(carrera.router)
app.include_router(admisiones.router)
app.include_router(digitaltwin.router)
app.include_router(papers.router)      # catálogo de papers + visor PDF inline
app.include_router(aes.router)         # AES (UC-1) — OCR + LLM-as-judge + calibración QWK
app.include_router(calidad.router)     # Calidad de datos — observabilidad DQX (uts_ops)


@app.get("/api/health")
def health():
    from server.config import CATALOG, IS_DATABRICKS_APP
    return {"ok": True, "catalog": CATALOG, "app_mode": IS_DATABRICKS_APP}


# ---- servir el SPA (frontend/dist) ----
DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(DIST, "index.html"))

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        fp = os.path.join(DIST, full_path)
        return FileResponse(fp) if os.path.isfile(fp) else FileResponse(os.path.join(DIST, "index.html"))
