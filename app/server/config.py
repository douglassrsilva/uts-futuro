"""Configuración dual-mode y auth — app Universidad Tecnológica de Sudamérica."""
import os
from functools import lru_cache

IS_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))

WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "032931930451e566")
CATALOG = os.environ.get("UTS_CATALOG", "classic_stable_douglas_s_catalog")
LAKEBASE_INSTANCE = os.environ.get("UTS_LAKEBASE_INSTANCE", "uts-lakebase")

# Model services del Unity AI Gateway (nombres UC de 3 niveles)
GW_CHAT = os.environ.get("UTS_GW_CHAT", f"{CATALOG}.uts_ml.uts-chat-gw")
GW_AGENT = os.environ.get("UTS_GW_AGENT", f"{CATALOG}.uts_ml.uts-agent-gw")
GW_JUDGE = os.environ.get("UTS_GW_JUDGE", f"{CATALOG}.uts_ml.uts-aes-judge")
GW_EMBED = os.environ.get("UTS_GW_EMBED", f"{CATALOG}.uts_ml.uts-embed-gw")
VS_ENDPOINT = os.environ.get("UTS_VS_ENDPOINT", "uts-vs")
GENIE_AGENT_ID = os.environ.get("UTS_GENIE_AGENT_ID", "")  # Genie Agent Mode (Beta), opcional
GENIE_SPACE_ID = os.environ.get("UTS_GENIE_SPACE_ID", "")  # fallback Genie clásico


@lru_cache(maxsize=1)
def get_workspace_client():
    from databricks.sdk import WorkspaceClient
    if IS_DATABRICKS_APP:
        return WorkspaceClient()
    return WorkspaceClient(profile=os.environ.get("DATABRICKS_PROFILE", "vibe-coding"))


def get_workspace_host():
    if IS_DATABRICKS_APP:
        host = os.environ.get("DATABRICKS_HOST", "")
        return host if host.startswith("http") else f"https://{host}"
    return get_workspace_client().config.host


def get_oauth_token():
    w = get_workspace_client()
    hdr = w.config.authenticate()
    if hdr and "Authorization" in hdr:
        return hdr["Authorization"].replace("Bearer ", "")
    return w.config.token


def extract_text(msg) -> str:
    """Extrae texto tolerando content str, lista de bloques (gpt-oss) o reasoning_content."""
    c = getattr(msg, "content", None)
    if isinstance(c, str) and c.strip():
        return c.strip()
    if isinstance(c, list):
        parts = []
        for blk in c:
            if isinstance(blk, dict):
                if blk.get("type") == "text" and blk.get("text"):
                    parts.append(blk["text"])
            else:
                t = getattr(blk, "text", None)
                if t and getattr(blk, "type", "text") == "text":
                    parts.append(t)
        if parts:
            return "\n".join(parts).strip()
    return (getattr(msg, "reasoning_content", None) or "").strip()


def llm_client(model: str):
    """Cliente OpenAI apuntando al Unity AI Gateway (nombre UC 3 niveles) o serving clásico."""
    from openai import OpenAI
    host = get_workspace_host()
    is_gateway = model.count(".") >= 2
    base = f"{host}/ai-gateway/mlflow/v1" if is_gateway else f"{host}/serving-endpoints"
    return OpenAI(api_key=get_oauth_token(), base_url=base)


def gw_chat(model: str, messages: list, max_tokens: int = 800) -> str:
    """Chat contra el Unity AI Gateway vía REST directo (nombre UC 3 niveles).

    Fuente única para TODAS las rutas que llaman a un model service Claude del Gateway.
    Por qué REST y no el SDK de OpenAI: el SDK deriva un model id estilo Bedrock
    (us.anthropic.claude-*) que el Gateway rechaza con 400 BAD_REQUEST. Pasar el nombre
    del model service UC directamente por REST es estable. Devuelve el texto (aplana
    bloques de contenido que Claude puede devolver como lista).

    NO se envía `temperature`/`top_p`/`top_k`: los model services de UTS enrutan a Claude
    Sonnet 5, que rechaza esos parámetros con 400 (Claude 4.6+/5). El determinismo se controla
    con el prompt, no con temperature."""
    import json as _json
    import urllib.request, urllib.error
    body = {"model": model, "max_tokens": max_tokens, "messages": messages}
    req = urllib.request.Request(
        f"{get_workspace_host()}/ai-gateway/mlflow/v1/chat/completions",
        data=_json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {get_oauth_token()}", "Content-Type": "application/json"})
    try:
        r = _json.load(urllib.request.urlopen(req, timeout=90))
    except urllib.error.HTTPError as e:
        # leer el cuerpo AQUÍ (una sola vez) y re-lanzar con el detalle embebido en el mensaje,
        # para que las rutas puedan clasificar (guardrail vs otro 400) sin volver a leer el stream.
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise RuntimeError(f"AI Gateway HTTP {e.code}: {detail[:400]}") from None
    c = r["choices"][0]["message"].get("content") or ""
    if isinstance(c, list):  # Claude vía Gateway puede devolver content como lista de bloques
        c = "".join(b.get("text", "") for b in c if isinstance(b, dict))
    return c


class GuardrailBlocked(Exception):
    """El guardrail del AI Gateway (block_jailbreak) rechazó la entrada con HTTP 400.
    NO es un fallo del sistema: es la defensa de la plataforma actuando ANTES del modelo.
    Las rutas la capturan y la presentan como 'requiere revisión humana', no como error."""


def is_guardrail_block(exc: Exception) -> bool:
    """¿El error es un bloqueo de guardrail (block_jailbreak/block_pii) y NO otro 400?

    gw_chat re-lanza los errores del Gateway como RuntimeError con el cuerpo embebido
    ('AI Gateway HTTP 400: {...}'). Un guardrail que deniega trae un mensaje específico; otros
    400 (p.ej. 'does not support the temperature parameter') son bugs de la petición, NO bloqueos
    de seguridad — no deben mostrarse al usuario como 'inyección'. Clasificamos por contenido."""
    msg = str(exc).lower()
    señales = ("guardrail", "jailbreak", "prompt injection", "block_pii", "block_jailbreak",
               "unsafe content", "blocked by", "content policy")
    return any(s in msg for s in señales)


@lru_cache(maxsize=1)
def sql_conn():
    """Conexión al SQL Warehouse (para leer gold)."""
    from databricks import sql
    host = get_workspace_host().replace("https://", "")
    return sql.connect(server_hostname=host,
                       http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
                       access_token=get_oauth_token())


def _run_query(sql_text: str, params: dict | None = None):
    with sql_conn().cursor() as cur:
        cur.execute(sql_text, parameters=params or {})
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def query(sql_text: str, params: dict | None = None):
    """Ejecuta SQL y devuelve lista de dicts.

    RESILIENCIA: la conexión al warehouse está cacheada (@lru_cache). Cuando el warehouse
    serverless se detiene por inactividad (auto-stop), ese socket TCP cacheado MUERE; la
    siguiente consulta lo reusa y falla con `RequestError: Error during request to server` en
    vez de abrir una conexión nueva (que dispararía el auto-start). Por eso, si una consulta
    falla, DESCARTAMOS la conexión cacheada y reintentamos una vez con una conexión fresca:
    esa reconexión despierta el warehouse y la consulta prospera.

    SEGURIDAD: para valores controlados por el usuario usa SIEMPRE consultas parametrizadas
    (marcadores `:nombre` + dict `params`), nunca f-strings. El databricks-sql-connector hace
    el binding/escaping del lado del servidor → inmune a inyección SQL. Los identificadores de
    catálogo/schema/tabla, que NO son parametrizables, provienen de config, no del usuario.
    """
    try:
        return _run_query(sql_text, params)
    except Exception:
        # conexión probablemente muerta (warehouse dormido / socket caído) → reconectar y reintentar
        try:
            sql_conn().close()
        except Exception:
            pass
        sql_conn.cache_clear()   # fuerza una conexión nueva (que despierta el warehouse)
        return _run_query(sql_text, params)


def read_volume_file(vol_path: str) -> bytes:
    """Lee un archivo de un Volumen UC. Files API primero (fiable en Apps; POSIX puede
    devolver 0 bytes si el volumen no está montado), con fallback POSIX."""
    files_err = None
    try:
        w = get_workspace_client()
        resp = w.files.download(vol_path)
        data = resp.contents.read()
        if data:
            return data
    except Exception as e:
        files_err = e
    # fallback POSIX (montaje del volumen en el runtime del app)
    try:
        with open(vol_path, "rb") as fh:
            return fh.read()
    except Exception as posix_err:
        raise RuntimeError(f"Files API: {files_err} · POSIX: {posix_err}")
