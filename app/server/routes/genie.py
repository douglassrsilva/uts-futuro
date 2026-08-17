"""Genie — Agent Mode API (agente de investigación multi-paso) con fallback al Genie clásico."""
import json
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ..config import get_workspace_client, GENIE_AGENT_ID, GENIE_SPACE_ID

router = APIRouter(prefix="/api", tags=["genie"])


def _agent_responses(pregunta, conversation_id=None):
    """Llama al Agent Mode API (/agents/{id}/responses). El endpoint puede responder JSON o
    un stream SSE (data: {...}); se maneja vía REST directo con stream=false y, si aun así
    llega SSE, se re-ensambla el último objeto 'response' de los eventos."""
    import urllib.request
    from ..config import get_workspace_host, get_oauth_token
    body = {"input": [{"type": "message", "role": "user",
                       "content": [{"type": "input_text", "text": pregunta}]}],
            "stream": False}
    if conversation_id:
        body["conversation_id"] = conversation_id
    req = urllib.request.Request(
        f"{get_workspace_host()}/api/2.0/genie/agents/{GENIE_AGENT_ID}/responses",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {get_oauth_token()}", "Content-Type": "application/json",
                 "Accept": "application/json"})
    raw = urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace").strip()
    # respuesta JSON directa
    try:
        return json.loads(raw)
    except Exception:
        pass
    # Stream SSE (formato real de la Genie Responses API): líneas `event:<tipo>` + `data:{...}`.
    # Los eventos `response.created` traen output=[] (vacío); el output se va completando en
    # eventos `response.output_item.added/.done` (cada uno con un `item`) y el objeto final llega
    # en `response.completed`.response.output. Estrategia robusta:
    #  1) si aparece un response con output NO vacío (p.ej. response.completed), usarlo tal cual;
    #  2) si no, RE-ENSAMBLAR el output a partir de los `item` de los eventos output_item.*.
    final_resp, cid, items = None, None, []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            ev = json.loads(payload)
        except Exception:
            continue
        resp = ev.get("response")
        if isinstance(resp, dict):
            cid = resp.get("conversation_id") or cid
            if resp.get("output"):                     # response.completed trae el output lleno
                final_resp = resp
        # acumular items (reasoning / message / function_call) de los eventos incrementales
        it = ev.get("item")
        if isinstance(it, dict) and it.get("type"):
            items.append(it)
    if final_resp:
        return final_resp
    # re-ensamblado: deduplicar items por id conservando el último estado de cada uno
    dedup = {}
    for it in items:
        dedup[it.get("id", id(it))] = it
    return {"output": list(dedup.values()), "conversation_id": cid}


def _normalizar_md(texto):
    """Arregla el markdown que devuelve el agente Genie para que renderice limpio:
    el agente pega el CAPTION (en **negrita**) de la tabla al final del título, en la MISMA
    línea (### 1. Título**Caption**). Lo separamos en dos líneas para que el heading quede
    limpio y el caption sea su propia línea (leyenda de la tabla que sigue)."""
    import re
    return re.sub(r'(?m)^(#{1,6}\s.*?)\*\*([^*\n]+)\*\*\s*$', r'\1\n\n*\2*', texto or "")


def _extract_sql(args):
    """Los arguments de una function_call vienen como JSON string; extrae el SQL."""
    if not args:
        return ""
    if isinstance(args, dict):
        return args.get("query") or args.get("sql") or ""
    try:
        d = json.loads(args)
        return d.get("query") or d.get("sql") or (args if isinstance(args, str) else "")
    except Exception:
        return args if isinstance(args, str) else ""


class GenieReq(BaseModel):
    pregunta: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=128)


@router.get("/genie/mode")
def mode():
    """Indica si el Agent Mode (Beta) está configurado o si se usa el Genie clásico."""
    return {"agent_mode": bool(GENIE_AGENT_ID), "space": bool(GENIE_SPACE_ID)}


@router.post("/genie/ask")
def ask(req: GenieReq):
    w = get_workspace_client()

    # --- Agent Mode API (Beta): investigación multi-paso con citas ---
    # El agente razona, ejecuta VARIAS consultas SQL y sintetiza un informe extenso.
    # Recogemos TODO (razonamiento + cada query + el texto final) para no perder el detalle.
    # IMPORTANTE: el Agent Mode es Beta y NO está habilitado en todos los workspaces (devuelve
    # 404). Si falla por eso, NO devolvemos error: caemos al Genie clásico (abajo), que sí está
    # disponible en cualquier workspace con un Genie space. Así el Genie del app funciona igual.
    if GENIE_AGENT_ID:
        try:
            r = _agent_responses(req.pregunta, req.conversation_id)
            texto, queries, pasos, cid = "", [], [], r.get("conversation_id")
            # pasos de razonamiento de bajo valor que no aportan al usuario (ruido del agente)
            _RUIDO = ("completing checklist", "writing final response", "reading", "planning")
            for item in r.get("output", []):
                it = item.get("type")
                if it == "message":   # respuesta final del agente (puede no traer role)
                    for blk in item.get("content", []):
                        if isinstance(blk, dict) and blk.get("type") in ("output_text", "text"):
                            texto += blk.get("text", "")
                elif it == "reasoning":
                    # cada paso de razonamiento del agente; blk puede ser reasoning_text/text
                    for blk in item.get("summary", []) or item.get("content", []):
                        s = blk.get("text", "") if isinstance(blk, dict) else str(blk)
                        s = (s or "").strip()
                        if s and not any(n in s.lower() for n in _RUIDO):
                            pasos.append(s)
                elif it == "function_call":
                    # cada consulta SQL que respalda el análisis
                    q = _extract_sql(item.get("arguments", ""))
                    if q:
                        queries.append(q)
            # sólo aceptamos la respuesta del agente si trajo algo; si vino vacía, probamos clásico
            if texto or queries:
                return {"modo": "agent", "texto": _normalizar_md(texto) or "(sin respuesta)",
                        "sql": queries[0] if queries else "", "queries": queries,
                        "pasos": pasos, "conversation_id": cid}
        except Exception as e:
            # Agent Mode no disponible (p.ej. 404 Not Found en workspaces sin la Beta) →
            # continuamos al Genie clásico en vez de romper.
            print(f"Genie Agent Mode no disponible ({str(e)[:120]}) → fallback al Genie clásico")

    # --- Genie clásico (start-conversation + poll) — disponible en cualquier workspace ---
    if GENIE_SPACE_ID:
        try:
            import time
            start = w.api_client.do("POST", f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}/start-conversation",
                                    body={"content": req.pregunta})
            cid, mid = start["conversation_id"], start["message_id"]
            for _ in range(30):
                m = w.api_client.do("GET", f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}/conversations/{cid}/messages/{mid}")
                if m.get("status") == "COMPLETED":
                    break
                time.sleep(2)
            texto = "".join(a.get("text", {}).get("content", "") for a in m.get("attachments", []))
            return {"modo": "clasico", "texto": texto or "(sin respuesta)", "conversation_id": cid}
        except Exception as e:
            return {"modo": "clasico", "error": str(e)[:200]}

    return {"modo": "no_configurado",
            "texto": "Genie aún no está configurado (falta el agent_id o space_id). Se habilita tras el deploy."}
