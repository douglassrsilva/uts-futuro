# 🎓 Universidad Tecnológica de Sudamérica (UTS) — Plataforma de Datos e IA

Golden demo **fim a fim** de una plataforma de datos e IA para educación superior en LATAM,
del **dato crudo** (Moodle + PeopleSoft) hasta un **app agéntico** (AES, retención, GraphRAG,
Genie, Digital Twin), sobre Databricks.

Este repo tiene **dos partes que se complementan**:

```
uts-futuro/
├── workshop/     ← 13 notebooks (ES) para RECONSTRUIR la plataforma paso a paso
│   ├── README.md            (guía del workshop + prerrequisitos)
│   ├── _comun.py            (config compartida: widgets catalog/schema_prefix/warehouse)
│   ├── notebooks/00..12     (datos → medallón+DQX → MDM → ML → AI Gateway → GraphRAG → Genie → app)
│   └── contracts/           (contratos de datos ODCS)
└── app/          ← código fuente del APP que consume todo lo anterior
    ├── frontend/            (React 18 + Vite + TS: App.tsx, componentes, i18n, styles)
    ├── server/              (FastAPI: config.py + routes/ — uno por feature)
    ├── app.yaml             (comando + variables de entorno del app)
    └── requirements.txt
```

## 🚀 Cómo usarlo (fim a fim)

1. **Reconstruye la plataforma** siguiendo `workshop/` (notebooks 00→11): crea los schemas
   `uts_*`, los datos sintéticos, el medallón con DQX, los modelos ML, el Unity AI Gateway,
   el Vector Search y el Genie space. Cada notebook está documentado y se parametriza con
   widgets (catálogo / prefijo / warehouse). Ver **`workshop/README.md`**.

2. **Despliega el app** siguiendo el **notebook 12** (`workshop/notebooks/12_despliegue_app.py`):
   compila `app/frontend`, crea la app con `databricks apps create/deploy` (standalone, **sin
   bundle**) y configura `app/app.yaml` con tus variables de entorno. El app sólo LEE lo que los
   notebooks crearon (tablas vía SQL Warehouse + model services + Vector Search + Genie).

> El código del app (`app/`) es lo que se despliega; los notebooks (`workshop/`) construyen la
> plataforma que el app consume. Reproducibles de forma independiente, pero pensados para usarse
> juntos en un workshop.

## ⚙️ Requisitos

- Workspace Databricks con **Unity Catalog**, un **SQL Warehouse** serverless y **serverless
  compute** para notebooks.
- Para el app y los módulos de IA: **Foundation Models**, **Vector Search**, **Databricks Apps**.
- Para el **Agente de Investigación** de Genie (Deep Research): habilitar las previews
  *"Agentic responses API"* + *"Deep Research"* (ver `workshop/README.md` y notebook 11).

---

*Todo el contenido es sintético y ficticio. Material en español (LATAM neutro).*
