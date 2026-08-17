async function get<T>(path: string): Promise<T> {
  const r = await fetch(path); if (!r.ok) throw new Error(`${r.status}`); return r.json()
}
async function post<T>(path: string, body: any): Promise<T> {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) throw new Error(`${r.status}`); return r.json()
}
export interface Cached<T> { data: T; fetched_at: number; cached: boolean }

export const api = {
  kpis: (refresh = false) => get<Cached<any>>(`/api/command/kpis?refresh=${refresh}`),
  campus: (refresh = false) => get<Cached<any[]>>(`/api/command/campus?refresh=${refresh}`),
  desercionPorCampus: () => get<Cached<any[]>>(`/api/command/desercion_por_campus`),
  // retención / 360 alumno
  dropoutList: (nivel = 'alto', campus = '') => get<any[]>(`/api/dropout/list?nivel=${nivel}&campus=${campus}&limit=60`),
  student: (id: string) => get<any>(`/api/student/${id}`),
  // graphrag
  graph: () => get<{ nodes: any[]; edges: any[] }>(`/api/graphrag/graph?limit=120`),
  ask: (pregunta: string, lang: string) => post<any>(`/api/graphrag/ask`, { pregunta, lang }),
  // carrera
  programas: () => get<any[]>(`/api/carrera/programas`),
  funilSemestre: (p = '') => get<any[]>(`/api/carrera/funil_semestre?programa=${p}`),
  abandonoSemestre: (p = '') => get<any[]>(`/api/carrera/abandono_semestre?programa=${p}`),
  carreraForecast: () => get<any[]>(`/api/carrera/forecast`),
  // admisiones
  admFunil: (campus = '') => get<any[]>(`/api/admisiones/funil?campus=${campus}`),
  admYield: () => get<any[]>(`/api/admisiones/yield`),
  admConversion: (dim = 'canal') => get<any[]>(`/api/admisiones/conversion?dim=${dim}`),
  admPostulantes: (etapa = '', canal = '') => get<any[]>(`/api/admisiones/postulantes?etapa=${etapa}&canal=${encodeURIComponent(canal)}`),
  admPropension: () => get<any[]>(`/api/admisiones/propension`),
  admNlp: (texto: string) => post<any>(`/api/admisiones/nlp`, { texto }),
  // campus individual + digital twin
  campusDetail: (cid: string) => get<any>(`/api/campus/${cid}`),
  twinEstado: () => get<any[]>(`/api/digitaltwin/estado`),
  twinSim: (crecimiento_pct: number, usar_forecast = true) => post<any>(`/api/digitaltwin/simulate`, { crecimiento_pct, usar_forecast }),
  // agente copiloto
  agente: (mensaje: string, lang: string, historial: any[] = []) => post<any>(`/api/agente/chat`, { mensaje, lang, historial }),
  sugerencias: (lang: string) => get<{ items: string[] }>(`/api/agente/sugerencias?lang=${lang}`),
  // papers
  papers: (q = '') => get<any[]>(`/api/papers?q=${encodeURIComponent(q)}`),
  paperPdfUrl: (id: string) => `/api/papers/${id}/pdf`,
  // genie
  genieAsk: (pregunta: string) => post<any>(`/api/genie/ask`, { pregunta }),
  // AES — automated essay scoring (UC-1)
  aesRedacciones: (estado = '', tipo = '') => get<any[]>(`/api/aes/redacciones?estado=${estado}&tipo=${tipo}`),
  aesRubrica: () => get<any[]>(`/api/aes/rubrica`),
  aesArchivoUrl: (id: string) => `/api/aes/archivo/${id}`,
  aesOcr: (id: string) => post<any>(`/api/aes/ocr/${id}`, {}),
  aesEvaluar: (essay_id: string, texto = '') => post<any>(`/api/aes/evaluar`, { essay_id, texto, persist: true }),
  aesCalibracion: () => get<any>(`/api/aes/calibracion`),
  // Calidad de datos — observabilidad DQX
  calidadResumen: () => get<any>(`/api/calidad/resumen`),
  calidadReglas: (contrato = '') => get<any[]>(`/api/calidad/reglas_contrato?contrato=${encodeURIComponent(contrato)}`),
  health: () => get<any>(`/api/health`),
}
