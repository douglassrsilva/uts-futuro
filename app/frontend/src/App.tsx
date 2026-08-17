import { useState, useEffect, useRef } from 'react'
import { makeT, Lang } from './i18n'
import { api } from './api'
import { LatamMap } from './components/LatamMap'
import { KnowledgeGraph } from './components/KnowledgeGraph'
import { Campus3D } from './components/Campus3D'
import { Copilot } from './components/Copilot'
import { Markdown } from './components/Markdown'
import { Logo, Loader } from './shared'

const NAV = [
  { k: 'copiloto', icon: 'M12 2a2 2 0 0 1 2 2v1a7 7 0 0 1 5 6.7V17l2 2v1H3v-1l2-2v-5.3A7 7 0 0 1 10 5V4a2 2 0 0 1 2-2z' },
  { k: 'home', icon: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z' },
  { k: 'aes', icon: 'M4 3h16v18l-4-3-4 3-4-3-4 3zM8 8h8M8 12h8M8 16h5' },
  { k: 'ret', icon: 'M3 3v18h18M7 14l4-4 3 3 5-6' },
  { k: 'carrera', icon: 'M22 10L12 4 2 10l10 6 10-6zM6 12v5c0 1 3 3 6 3s6-2 6-3v-5' },
  { k: 'adm', icon: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 11l-3 3-2-2' },
  { k: 'campus', icon: 'M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6' },
  { k: 'twin', icon: 'M12 2l9 5v10l-9 5-9-5V7zM12 12l9-5M12 12v10M12 12L3 7' },
  { k: 'chat', icon: 'M21 11a8 8 0 1 1-8-8M12 12l9-9M17 3h4v4' },
  { k: 'genie', icon: 'M12 2l2.4 6.5H21l-5.2 4 2 6.5-5.8-4-5.8 4 2-6.5-5.2-4h6.6z' },
  { k: 'calidad', icon: 'M9 12l2 2 4-4M12 3l7 4v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V7z' },
]

export default function App() {
  const [lang, setLang] = useState<Lang>('es')
  const [view, setView] = useState('copiloto')
  const [studentId, setStudentId] = useState<string | null>(null)
  const t = makeT(lang)
  useEffect(() => { document.documentElement.lang = lang }, [lang])
  const goStudent = (id: string) => { setStudentId(id); setView('student') }

  return (
    <div className="app">
      <nav className="topnav">
        <div className="brand"><Logo /><div className="nm">Universidad Tecnológica<small>de Sudamérica</small></div></div>
        <div className="navpills">
          {NAV.map(n => (
            <button key={n.k} className={`np ${view === n.k ? 'on' : ''}`} onClick={() => setView(n.k)} title={t('nav_' + n.k)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d={n.icon} /></svg>
              <span className="lbl">{t('nav_' + n.k)}</span>
            </button>
          ))}
        </div>
        <div className="navr">
          <div className="seg"><button className={lang === 'es' ? 'on' : ''} onClick={() => setLang('es')}>ES</button><button className={lang === 'pt' ? 'on' : ''} onClick={() => setLang('pt')}>PT</button></div>
          <div className="av">DS</div>
        </div>
      </nav>

      {view === 'copiloto' && <Copilot t={t} lang={lang} goStudent={goStudent} />}
      {view === 'home' && <Home t={t} lang={lang} goStudent={goStudent} />}
      {view === 'aes' && <Redacciones t={t} lang={lang} />}
      {view === 'ret' && <Retencion t={t} goStudent={goStudent} />}
      {view === 'student' && <Student360 t={t} id={studentId} back={() => setView('ret')} />}
      {view === 'carrera' && <Carrera t={t} />}
      {view === 'adm' && <Admisiones t={t} />}
      {view === 'campus' && <Campus t={t} />}
      {view === 'twin' && <DigitalTwin t={t} />}
      {view === 'chat' && <GraphExplorer t={t} lang={lang} />}
      {view === 'genie' && <GenieView t={t} />}
      {view === 'calidad' && <Calidad t={t} />}
    </div>
  )
}

// ============ CALIDAD DE DATOS — observabilidad DQX ============
function Calidad({ t }: any) {
  const [d, setD] = useState<any>(null)
  const [reglas, setReglas] = useState<any[]>([])
  useEffect(() => {
    api.calidadResumen().then(setD).catch(() => setD({ error: 1 }))
    api.calidadReglas().then(setReglas).catch(() => {})
  }, [])
  if (!d) return <div style={{ marginTop: 40 }}><Loader t={t} /></div>
  const k = d.kpis || {}
  const col = (pct: number) => pct > 5 ? 'var(--crit)' : pct > 1 ? 'var(--gold)' : 'var(--good)'
  return (
    <><div className="eyebrow" style={{ marginTop: 26 }}>Calidad de datos · DQX (Databricks Labs)</div>
      <h1 style={{ fontSize: 34 }}>{t('cal_t')}</h1>
      <div className="sub">{t('cal_sub')}</div>

      <div className="kpirow" style={{ marginTop: 14 }}>
        <div className="glass kpi"><div className="k">{t('cal_cuar')}</div><div className="v" style={{ color: col(k.tasa_cuarentena_global) }}>{k.tasa_cuarentena_global}%</div><div className="ksub">get_valid / get_invalid</div></div>
        <div className="glass kpi"><div className="k">{t('cal_pii')}</div><div className="v" style={{ color: k.columnas_con_pii > 0 ? 'var(--gold)' : 'var(--good)' }}>{k.columnas_con_pii}</div><div className="ksub">does_not_contain_pii</div></div>
        <div className="glass kpi"><div className="k">{t('cal_anom')}</div><div className="v" style={{ color: k.filas_anomalas > 0 ? 'var(--gold)' : 'var(--good)' }}>{k.filas_anomalas}</div><div className="ksub">AnomalyEngine · p97</div></div>
        <div className="glass kpi"><div className="k">{t('cal_reglas')}</div><div className="v" style={{ color: 'var(--violet-2)' }}>{k.reglas_desde_contratos}</div><div className="ksub">ODCS → DQX</div></div>
      </div>

      <div className="bento">
        {/* Cuarentena por tabla */}
        <div className="glass c-half">
          <div className="hd"><span className="t">{t('cal_cuar_t')}</span><span className="b">DQEngine</span></div>
          <table className="tbl"><thead><tr><th>Tabla</th><th>Válidos</th><th>Cuarentena</th><th>Tasa</th></tr></thead>
            <tbody>{(d.cuarentena || []).map((r: any, i: number) => (
              <tr key={i}><td style={{ color: 'var(--txt)' }}>{r.tabla}</td><td>{r.validos}</td><td>{r.cuarentena}</td>
                <td><span className={`pill ${r.tasa_cuarentena_pct > 5 ? 'alto' : r.tasa_cuarentena_pct > 1 ? 'medio' : 'bajo'}`}>{r.tasa_cuarentena_pct}%</span></td></tr>
            ))}</tbody></table>
        </div>
        {/* PII — checks aplicados en el pipeline silver */}
        <div className="glass c-half">
          <div className="hd"><span className="t">{t('cal_pii_t')}</span><span className="b">Presidio · gating silver</span></div>
          {(d.pii || []).length ? (
            <table className="tbl"><thead><tr><th>Check</th><th>Función</th><th>Crit.</th><th>Columna</th></tr></thead>
              <tbody>{(d.pii || []).map((r: any, i: number) => (
                <tr key={i}><td style={{ color: 'var(--txt)' }}>{r.check}</td><td style={{ fontSize: 11 }}>{r.funcion}</td>
                  <td><span className={`pill ${r.criticidad === 'error' ? 'alto' : 'medio'}`}>{r.criticidad}</span></td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--txt-3)' }}>{(r.argumentos || '').slice(0, 40)}</td></tr>
              ))}</tbody></table>
          ) : <div style={{ color: 'var(--txt-3)', fontSize: 12, padding: 14 }}>{t('cal_pii_none')}</div>}
        </div>
      </div>

      <div className="bento">
        {/* Primary Key detection */}
        <div className="glass c-half">
          <div className="hd"><span className="t">{t('cal_pk_t')}</span><span className="b">LLM · claude-sonnet</span></div>
          <table className="tbl"><thead><tr><th>Tabla</th><th>Primary Key detectada</th><th>Conf.</th></tr></thead>
            <tbody>{(d.primary_keys || []).map((r: any, i: number) => (
              <tr key={i}><td style={{ color: 'var(--txt)' }}>{r.tabla}</td>
                <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{r.primary_key}</td>
                <td>{r.confianza < 0 ? '—' : `${Math.round(r.confianza * 100)}%`}</td></tr>
            ))}</tbody></table>
        </div>
        {/* Anomaly detection */}
        <div className="glass c-half">
          <div className="hd"><span className="t">{t('cal_anom_t')}</span><span className="b">has_no_row_anomalies</span></div>
          <table className="tbl"><thead><tr><th>Modelo</th><th>Dataset</th><th>Filas</th><th>Anómalas</th></tr></thead>
            <tbody>{(d.anomaly || []).map((r: any, i: number) => (
              <tr key={i}><td style={{ color: 'var(--txt)', fontSize: 11 }}>{r.modelo}</td><td style={{ fontSize: 11 }}>{r.dataset}</td>
                <td>{r.filas_total < 0 ? '—' : r.filas_total}</td>
                <td><span className={`pill ${r.filas_anomalas > 0 ? 'medio' : 'bajo'}`}>{r.filas_anomalas < 0 ? '—' : r.filas_anomalas}</span></td></tr>
            ))}</tbody></table>
        </div>
      </div>

      {/* Reglas generadas desde contratos ODCS */}
      <div className="glass c-full" style={{ marginTop: 14 }}>
        <div className="hd"><span className="t">{t('cal_reglas_t')}</span><span className="b">{reglas.length} reglas · ODCS v3.x → DQX</span></div>
        <table className="tbl"><thead><tr><th>Contrato</th><th>Regla</th><th>Función DQX</th><th>Crit.</th><th>Argumentos</th></tr></thead>
          <tbody>{reglas.slice(0, 40).map((r, i) => (
            <tr key={i}><td style={{ fontSize: 11 }}>{r.contrato}</td><td style={{ color: 'var(--txt)', fontSize: 11 }}>{r.regla}</td>
              <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{r.funcion}</td>
              <td><span className={`pill ${r.criticidad === 'error' ? 'alto' : 'medio'}`}>{r.criticidad}</span></td>
              <td style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--txt-3)' }}>{(r.argumentos || '').slice(0, 60)}</td></tr>
          ))}</tbody></table>
      </div></>
  )
}

function Fresh({ at, onRefresh, busy, t }: any) {
  const mins = at ? Math.floor((Date.now() / 1000 - at) / 60) : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <span className={`fresh ${mins >= 1 ? 'stale' : ''}`}><span className="dot" />{t('updated')} {mins <= 0 ? (lang0 = 'ahora') : `hace ${mins}m`}</span>
      <button className="refresh" onClick={onRefresh} disabled={busy}><span className={busy ? 'loading' : ''}><Logo size={14} /></span>{t('refresh')}</button>
    </div>
  )
}
let lang0 = 'ahora'

// ============ HOME — Centro de Mando acionável ============
function Home({ t, lang, goStudent }: any) {
  const [kpis, setKpis] = useState<any>(null)
  const [desCampus, setDesCampus] = useState<any[]>([])
  const [risk, setRisk] = useState<any[]>([])
  const [graph, setGraph] = useState<any>(null)
  const [busy, setBusy] = useState(false); const [at, setAt] = useState(0)

  const load = async (refresh = false) => {
    setBusy(true)
    try {
      const [k, d, r] = await Promise.all([api.kpis(refresh), api.desercionPorCampus(), api.dropoutList('alto')])
      setKpis(k.data); setDesCampus(d.data || []); setRisk(r.slice(0, 5)); setAt(k.fetched_at)
      if (!graph) api.graph().then(setGraph).catch(() => {})
    } finally { setBusy(false) }
  }
  useEffect(() => { load() }, [])

  return (
    <>
      <div className="eyebrow">Plataforma de datos e IA · en vivo</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 16 }}>
        <div><h1>{t('h1a')} <span className="g">{t('h1b')}</span></h1><div className="sub">{t('sub')}</div></div>
        <Fresh at={at} onRefresh={() => load(true)} busy={busy} t={t} />
      </div>

      {/* KPIs con decisión */}
      <div className="kpirow">
        {kpis ? [
          { k: t('k_matricula'), v: kpis.matricula?.toLocaleString('es'), sub: '8 campus · LATAM', c: '#F4F3FA' },
          { k: t('k_riesgo'), v: kpis.en_riesgo, sub: `${((kpis.tasa_desercion || 0) * 100).toFixed(1)}% ${t('tasa')}`, c: '#FF6B7A' },
          { k: t('k_ocup'), v: (kpis.ocupacion_media || 0) + '%', sub: t('k_ocup_sub'), c: '#F4F3FA' },
          { k: t('k_qwk'), v: kpis.qwk, sub: t('qwk_sub'), c: '#9C84FF' },
        ].map((s, i) => <div key={i} className="glass kpi"><div className="k">{s.k}</div><div className="v" style={{ color: s.c }}>{s.v}</div><div className="ksub">{s.sub}</div></div>)
          : <div className="glass" style={{ gridColumn: '1/-1' }}><Loader t={t} /></div>}
      </div>

      <div className="bento">
        {/* Acciones prioritarias — la decisión */}
        <div className="glass c-actions">
          <div className="hd"><span className="t">◆ {t('acciones')}</span><span className="b">{t('acciones_sub')}</span></div>
          <div className="actionlist">
            {risk.map((r, i) => (
              <div key={i} className="actionrow" onClick={() => goStudent(r.student_master_id)}>
                <div className="ar-l"><div className="ar-name">{r.nombre}</div><div className="ar-meta">{r.program_name} · {r.ciudad}</div></div>
                <div className="ar-r"><span className="ar-factor">{r.factor_principal}</span><span className="ar-score">{Math.round(r.riesgo_score * 100)}%</span><span className="ar-go">→</span></div>
              </div>
            ))}
            {desCampus.length > 0 && <div className="ar-insight">💡 {t('insight_pre')} <b>{desCampus[0]?.Campus}</b> {t('insight_pos')} {((desCampus[0]?.tasa || 0) * 100).toFixed(1)}%.</div>}
          </div>
        </div>
        {/* Grafo de conocimiento (vivo) */}
        <div className="glass c-graph">
          <div className="hd"><span className="t">{t('grafo_t')}</span><span className="b">{graph ? `${graph.nodes?.length} nodos` : '…'}</span></div>
          <KnowledgeGraph data={graph} height={230} />
        </div>
      </div>
    </>
  )
}

// ============ AES — Redacciones (núcleo): OCR + LLM-as-judge + calibración QWK ============
function Redacciones({ t, lang }: any) {
  const [rows, setRows] = useState<any[] | null>(null)
  const [tipo, setTipo] = useState('')
  const [sel, setSel] = useState<any>(null)
  const [cal, setCal] = useState<any>(null)
  const load = () => { setRows(null); api.aesRedacciones('', tipo).then(setRows).catch(() => setRows([])) }
  useEffect(load, [tipo])
  useEffect(() => { api.aesCalibracion().then(setCal).catch(() => {}) }, [])
  const n = rows?.length || 0
  const evaluadas = rows?.filter(r => r.nota_ia != null).length || 0
  return (
    <><div className="eyebrow" style={{ marginTop: 26 }}>AES · corrección automática de redacciones (LLM-as-judge + OCR)</div>
      <div className="viewhd"><h1 style={{ fontSize: 34 }}>{t('aes_t')}</h1>
        <div className="seg">{[['', 'todas'], ['digital', 'digital'], ['manuscrito', 'manuscrito']].map(([k, l]) =>
          <button key={k} className={tipo === k ? 'on' : ''} onClick={() => setTipo(k)}>{l}</button>)}</div></div>
      <div className="sub">{t('aes_sub')}</div>

      {/* KPIs de la cola + calibración QWK */}
      <div className="kpirow" style={{ marginTop: 14 }}>
        <div className="glass kpi"><div className="k">{t('aes_cola')}</div><div className="v">{n}</div><div className="ksub">{evaluadas} {t('aes_evaluadas')}</div></div>
        <div className="glass kpi"><div className="k">QWK</div><div className="v" style={{ color: cal?.qwk >= 0.7 ? 'var(--good)' : cal?.qwk >= 0.4 ? 'var(--gold)' : '#9C84FF' }}>{cal?.qwk ?? '—'}</div><div className="ksub">{t('aes_qwk_sub')}</div></div>
        <div className="glass kpi"><div className="k">MAE</div><div className="v">{cal?.mae ?? '—'}</div><div className="ksub">{t('aes_mae_sub')} · n={cal?.n ?? 0}</div></div>
        <div className="glass kpi"><div className="k">OCR</div><div className="v" style={{ fontSize: 20 }}>Vision + parse</div><div className="ksub">{t('aes_ocr_sub')}</div></div>
      </div>

      <div className="glass c-full" style={{ marginTop: 16 }}>
        {!rows ? <Loader t={t} /> : (
          <table className="tbl"><thead><tr><th>{t('col_alumno')}</th><th>{t('aes_tema')}</th><th>{t('aes_tipo')}</th><th>{t('aes_humana')}</th><th>{t('aes_ia')}</th><th>{t('aes_estado')}</th><th></th></tr></thead>
            <tbody>{rows.map((r, i) => (
              <tr key={i} className="clickrow" onClick={() => setSel(r)}>
                <td style={{ color: 'var(--txt)' }}>{r.alumno || r.student_id}</td>
                <td style={{ fontSize: 11, maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.tema}</td>
                <td><span className={`pill ${r.tipo === 'manuscrito' ? 'medio' : 'bajo'}`}>{r.tipo}</span></td>
                <td style={{ fontFamily: 'var(--mono)' }}>{r.nota_humana}</td>
                <td style={{ fontFamily: 'var(--mono)', color: r.nota_ia != null ? 'var(--violet-2)' : 'var(--txt-3)' }}>{r.nota_ia ?? '—'}</td>
                <td><span className={`pill ${r.estado === 'evaluado' ? 'bajo' : 'medio'}`}>{r.estado}</span></td>
                <td className="ar-go">→</td></tr>
            ))}</tbody></table>
        )}
      </div>
      {sel && <EssayGrader t={t} lang={lang} essay={sel} onClose={() => { setSel(null); load(); api.aesCalibracion().then(setCal) }} />}
    </>
  )
}

function EssayGrader({ t, lang, essay, onClose }: any) {
  const [texto, setTexto] = useState('')
  const [ocrBusy, setOcrBusy] = useState(false); const [ocrMeta, setOcrMeta] = useState('')
  const [score, setScore] = useState<any>(null); const [busy, setBusy] = useState(false)
  const esManuscrito = essay.tipo === 'manuscrito'
  useEffect(() => {
    // auto-OCR al abrir
    setOcrBusy(true)
    api.aesOcr(essay.essay_id).then(r => { setTexto(r.texto || ''); setOcrMeta(r.metodo || '') }).catch(() => {}).finally(() => setOcrBusy(false))
  }, [essay.essay_id])
  const evaluar = async () => { setBusy(true); try { setScore(await api.aesEvaluar(essay.essay_id, texto)) } finally { setBusy(false) } }
  return (
    <div className="pdfmodal" onClick={onClose}>
      <div className="pdfbox" onClick={e => e.stopPropagation()} style={{ width: 'min(1100px,95vw)', maxWidth: '95vw' }}>
        <div className="pdfhd"><div><b>{essay.alumno || essay.student_id}</b><div className="pp-m">{essay.tema} · {essay.tipo}</div></div><button onClick={onClose}>✕</button></div>
        <div className="graderbody">
          {/* Panel izq: el documento original */}
          <div className="grader-doc">
            {esManuscrito
              ? <img src={api.aesArchivoUrl(essay.essay_id)} alt="manuscrito" className="grader-img" />
              : <iframe src={api.aesArchivoUrl(essay.essay_id)} title="essay" className="pdfframe" style={{ height: 440 }} />}
            <div className="grader-ocr">
              <div className="hd"><span className="t">{t('aes_transcripcion')}</span><span className="b">{ocrBusy ? 'OCR…' : ocrMeta}</span></div>
              <textarea className="essay" value={texto} onChange={e => setTexto(e.target.value)} style={{ minHeight: 120 }} placeholder={ocrBusy ? 'Extrayendo texto…' : ''} />
            </div>
          </div>
          {/* Panel der: la evaluación */}
          <div className="grader-score">
            {!score ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div className="grader-hint">{t('aes_hint')}</div>
                <button className="cta" onClick={evaluar} disabled={busy || !texto.trim()}>{busy ? t('loading') : `◆ ${t('aes_evaluar_btn')}`}</button>
                {essay.nota_ia != null && <div className="grader-prev">{t('aes_prev')}: <b style={{ color: 'var(--violet-2)' }}>{essay.nota_ia}</b> / 20 · {t('aes_humana')}: <b>{essay.nota_humana}</b></div>}
              </div>
            ) : (
              <>
                <div className="grader-notas">
                  <div className="gn-ia"><div className="gn-k">{t('aes_nota_ia')}</div><div className="gn-v">{score.nota_ia}<small>/20</small></div></div>
                  <div className="gn-h"><div className="gn-k">{t('aes_humana')}</div><div className="gn-v">{score.nota_humana ?? '—'}<small>/20</small></div></div>
                  <div className="gn-d"><div className="gn-k">Δ</div><div className="gn-v" style={{ color: Math.abs((score.nota_ia || 0) - (score.nota_humana || 0)) <= 2 ? 'var(--good)' : 'var(--gold)' }}>{score.nota_humana != null ? (score.nota_ia - score.nota_humana).toFixed(1) : '—'}</div></div>
                </div>
                {score.integridad === 'sospecha_inyeccion' && <div className="grader-warn">⚠ {t('aes_inyeccion')}{score.inyeccion_detectada?.length ? `: "${score.inyeccion_detectada[0]}"` : ''}</div>}
                <div className="grader-rubric">
                  {score.criterios.map((c: any, i: number) => (
                    <div key={i} className="gr-row">
                      <div className="gr-hd"><span>{c.criterio}</span><b>{c.nota}/{c.peso}</b></div>
                      <div className="track"><div className="fill" style={{ width: `${c.nota / c.peso * 100}%`, background: c.nota / c.peso >= 0.7 ? 'var(--good)' : c.nota / c.peso >= 0.4 ? 'var(--gold)' : 'var(--crit)' }} /></div>
                      <div className="gr-just">{c.justificacion}</div>
                    </div>
                  ))}
                </div>
                <div className="accion"><b>◆ {t('aes_retro')}:</b> {score.retroalimentacion}</div>
                <button className="cta ghost" onClick={() => setScore(null)} style={{ marginTop: 10 }}>{t('aes_reevaluar')}</button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ============ RETENCIÓN — lista → drill 360 ============
function Retencion({ t, goStudent }: any) {
  const [rows, setRows] = useState<any[] | null>(null)
  const [nivel, setNivel] = useState('alto')
  useEffect(() => { setRows(null); api.dropoutList(nivel).then(setRows).catch(() => setRows([])) }, [nivel])
  return (
    <><div className="eyebrow" style={{ marginTop: 26 }}>Retención · ML + SHAP</div>
      <div className="viewhd"><h1 style={{ fontSize: 34 }}>{t('ret_t')}</h1>
        <div className="seg">{['alto', 'medio', 'bajo'].map(n => <button key={n} className={nivel === n ? 'on' : ''} onClick={() => setNivel(n)}>{n}</button>)}</div></div>
      <div className="glass c-full" style={{ marginTop: 16 }}>
        {!rows ? <Loader t={t} /> : (
          <table className="tbl"><thead><tr><th>{t('col_alumno')}</th><th>{t('col_prog')}</th><th>Campus</th><th>Sem.</th><th>{t('ret_score')}</th><th>{t('ret_factor')}</th><th></th></tr></thead>
            <tbody>{rows.slice(0, 40).map((r, i) => (
              <tr key={i} className="clickrow" onClick={() => goStudent(r.student_master_id)}>
                <td style={{ color: 'var(--txt)' }}>{r.nombre}</td><td>{r.program_name}</td><td>{r.ciudad}</td><td>{r.semestre}</td>
                <td><span className="scorebadge" style={{ '--p': `${r.riesgo_score * 100}%` } as any}>{Math.round(r.riesgo_score * 100)}%</span></td>
                <td><span className={`pill ${r.riesgo_nivel}`}>{r.factor_principal}</span></td>
                <td className="ar-go">→</td></tr>
            ))}</tbody></table>
        )}
      </div></>
  )
}

// ============ 360 DEL ALUMNO ============
function Student360({ t, id, back }: any) {
  const [d, setD] = useState<any>(null)
  useEffect(() => { setD(null); if (id) api.student(id).then(setD).catch(() => setD({ error: 1 })) }, [id])
  if (!d) return <div style={{ marginTop: 40 }}><Loader t={t} /></div>
  if (d.error) return <div style={{ marginTop: 40 }}>No encontrado. <a onClick={back} style={{ cursor: 'pointer', color: 'var(--violet-2)' }}>← volver</a></div>
  const p = d.perfil, r = d.riesgo || {}
  const shap = r.shap || []
  const maxc = Math.max(...shap.map((s: any) => Math.abs(s.contrib)), 0.01)
  return (
    <><div className="eyebrow" style={{ marginTop: 26 }}><a onClick={back} style={{ cursor: 'pointer' }}>← {t('volver')}</a> · Estudiante 360</div>
      <h1 style={{ fontSize: 32 }}>{p.nombre}</h1>
      <div className="sub">{p.program_name} · {p.ciudad}, {p.pais_nombre} · {t('semestre')} {p.semestre} · {p.moneda}</div>
      <div className="bento360">
        <div className="glass card360"><div className="c360-k">GPA</div><div className="c360-v">{p.gpa}</div><div className="c360-s">/ 20</div></div>
        <div className="glass card360"><div className="c360-k">{t('mora')}</div><div className="c360-v" style={{ color: p.dias_mora > 30 ? 'var(--crit)' : 'var(--txt)' }}>{p.dias_mora}d</div><div className="c360-s">${Math.round(p.saldo_vencido)}</div></div>
        <div className="glass card360"><div className="c360-k">{t('trabaja')}</div><div className="c360-v">{p.gente_trabaja ? 'Sí' : 'No'}</div></div>
        <div className="glass card360" style={{ borderColor: r.riesgo_nivel === 'alto' ? 'var(--stroke-hi)' : 'var(--stroke)' }}>
          <div className="c360-k">{t('k_riesgo')}</div><div className="c360-v" style={{ color: r.riesgo_nivel === 'alto' ? 'var(--crit)' : r.riesgo_nivel === 'medio' ? 'var(--gold)' : 'var(--good)' }}>{Math.round((r.riesgo_score || 0) * 100)}%</div><div className="c360-s">{r.riesgo_nivel}</div></div>
      </div>
      <div className="bento">
        {/* SHAP waterfall — POR QUÉ está en riesgo */}
        <div className="glass c-half">
          <div className="hd"><span className="t">{t('porque_riesgo')}</span><span className="b">{r.shap_metodo || 'SHAP'}</span></div>
          <div className="shapwrap">
            {shap.map((s: any, i: number) => (
              <div key={i} className="shaprow"><div className="shap-lbl">{s.label}</div>
                <div className="shap-bar"><div className="shap-fill" style={{ width: `${Math.abs(s.contrib) / maxc * 100}%`, background: s.contrib > 0 ? 'var(--crit)' : 'var(--good)' }} /></div>
                <div className="shap-val" style={{ color: s.contrib > 0 ? 'var(--crit)' : 'var(--good)' }}>{s.contrib > 0 ? '+' : ''}{s.contrib.toFixed(3)}</div></div>
            ))}
          </div>
          <div className="accion"><b>◆ {t('accion')}:</b> {d.accion_recomendada}
            {r.semestre_critico && <div className="accion-sem">{t('sem_critico')}: <b>{t('semestre')} {r.semestre_critico}</b></div>}</div>
        </div>
        {/* Notas + trayectoria */}
        <div className="glass c-half">
          <div className="hd"><span className="t">{t('notas_curso')}</span></div>
          {(d.notas || []).map((n: any, i: number) => (
            <div className="occrow" key={i}><div className="cn" style={{ width: 130 }}>{n.course_title}</div>
              <div className="track"><div className="fill" style={{ width: `${n.nota / 20 * 100}%`, background: n.nota < 11 ? 'var(--crit)' : n.nota < 14 ? 'var(--gold)' : 'var(--good)', color: n.nota < 11 ? 'var(--crit)' : 'var(--good)' }} /></div>
              <div className="p">{n.nota}</div></div>
          ))}
          {!(d.notas || []).length && <div style={{ color: 'var(--txt-3)', fontSize: 12, padding: 12 }}>Sin notas registradas.</div>}
        </div>
      </div></>
  )
}

// ============ CARRERA 360 ============
function Carrera({ t }: any) {
  const [progs, setProgs] = useState<any[] | null>(null)
  const [aband, setAband] = useState<any[]>([])
  const [funil, setFunil] = useState<any[]>([])
  useEffect(() => {
    api.programas().then(setProgs).catch(() => setProgs([]))
    api.abandonoSemestre().then(setAband).catch(() => {})
    api.funilSemestre().then(setFunil).catch(() => {})
  }, [])
  const maxF = Math.max(...funil.map(f => f.alumnos), 1)
  const maxA = Math.max(...aband.map(a => a.en_riesgo), 1)
  return (
    <><div className="eyebrow" style={{ marginTop: 26 }}>Carrera 360 · crecimiento · forecast · funil</div>
      <h1 style={{ fontSize: 34 }}>{t('carrera_t')}</h1>
      <div className="bento">
        <div className="glass c-half">
          <div className="hd"><span className="t">{t('funil_sem')}</span><span className="b">{t('progresion')}</span></div>
          <div className="funil">{funil.map(f => (
            <div key={f.semestre} className="funil-row"><span className="fs-lbl">S{f.semestre}</span>
              <div className="fs-bar"><div className="fs-fill" style={{ width: `${f.alumnos / maxF * 100}%` }}>{f.alumnos}</div></div></div>
          ))}</div>
        </div>
        <div className="glass c-half">
          <div className="hd"><span className="t">{t('aband_sem')}</span><span className="b">{t('donde_evade')}</span></div>
          <div className="funil">{aband.map(a => (
            <div key={a.semestre} className="funil-row"><span className="fs-lbl">S{a.semestre}</span>
              <div className="fs-bar"><div className="fs-fill" style={{ width: `${a.en_riesgo / maxA * 100}%`, background: 'linear-gradient(90deg,#FF6B7A,#F5C86B)' }}>{a.en_riesgo}</div></div></div>
          ))}</div>
        </div>
      </div>
      <div className="glass c-full" style={{ marginTop: 14 }}>
        <div className="hd"><span className="t">{t('programas')}</span><span className="b">{progs?.length || 0}</span></div>
        {!progs ? <Loader t={t} /> : (
          <table className="tbl"><thead><tr><th>{t('col_prog')}</th><th>Área ISCED-F</th><th>{t('col_alumnos')}</th><th>GPA</th><th>{t('tasa_riesgo')}</th></tr></thead>
            <tbody>{progs.map((p, i) => (
              <tr key={i}><td style={{ color: 'var(--txt)' }}>{p.program_name}</td><td style={{ fontSize: 11 }}>{p.isced_f}</td><td>{p.alumnos}</td><td>{p.gpa_medio}</td>
                <td><span className={`pill ${p.tasa_riesgo > 0.05 ? 'alto' : p.tasa_riesgo > 0.02 ? 'medio' : 'bajo'}`}>{(p.tasa_riesgo * 100).toFixed(1)}%</span></td></tr>
            ))}</tbody></table>
        )}
      </div></>
  )
}

// ============ ADMISIONES (business case) ============
function Admisiones({ t }: any) {
  const [funil, setFunil] = useState<any[]>([])
  const [conv, setConv] = useState<any[]>([]); const [dim, setDim] = useState('canal')
  const [drill, setDrill] = useState<string>('')            // etapa seleccionada → drill de postulantes
  const [gente, setGente] = useState<any[] | null>(null)
  const [nlp, setNlp] = useState<any>(null); const [essay, setEssay] = useState(''); const [busy, setBusy] = useState(false)
  useEffect(() => {
    api.admFunil().then(setFunil).catch(() => setTimeout(() => api.admFunil().then(setFunil).catch(() => {}), 1500))
  }, [])
  useEffect(() => { api.admConversion(dim).then(setConv).catch(() => {}) }, [dim])
  useEffect(() => {
    if (!drill) { setGente(null); return }
    setGente(null); api.admPostulantes(drill).then(setGente).catch(() => setGente([]))
  }, [drill])
  const analizar = async () => { if (!essay.trim()) return; setBusy(true); try { setNlp(await api.admNlp(essay)) } finally { setBusy(false) } }
  const top = funil[0]?.n || 1
  const ETAPA_LABEL: any = { PROSPECTO: 'Prospectos', 'POSTULÓ': 'Postularon', ADMITIDO: 'Admitidos', 'MATRICULÓ': 'Matricularon' }
  const DIMS = [['canal', 'Canal'], ['programa', 'Programa'], ['campus', 'Campus'], ['pais', 'País']]
  return (
    <><div className="eyebrow" style={{ marginTop: 26 }}>Admisiones · captación · conversión · propensión</div>
      <h1 style={{ fontSize: 34 }}>{t('adm_t')}</h1>
      <div className="sub">Del prospecto a la matrícula: dónde se fuga el embudo, quién está en cada etapa y por qué canal convertimos mejor.</div>

      {/* KPIs de conversión global */}
      <div className="kpirow" style={{ marginTop: 14 }}>
        {funil.length === 4 && [
          { k: 'Prospectos', v: funil[0].n.toLocaleString('es'), sub: 'tope del embudo', c: '#F4F3FA' },
          { k: 'Postularon', v: funil[1].n.toLocaleString('es'), sub: `${funil[1].conv_paso}% del anterior`, c: '#9C84FF' },
          { k: 'Admitidos', v: funil[2].n.toLocaleString('es'), sub: `${funil[2].conv_paso}% de postulantes`, c: '#F5C86B' },
          { k: 'Matricularon', v: funil[3].n.toLocaleString('es'), sub: `${funil[3].conv_desde_inicio}% conversión total`, c: '#31E1D6' },
        ].map((s, i) => <div key={i} className="glass kpi"><div className="k">{s.k}</div><div className="v" style={{ color: s.c }}>{s.v}</div><div className="ksub">{s.sub}</div></div>)}
      </div>

      <div className="bento">
        {/* Funil de conversión — clicable (drill a quiénes están en la etapa) */}
        <div className="glass c-half">
          <div className="hd"><span className="t">Embudo de conversión</span><span className="b">click en una etapa → ver quiénes</span></div>
          <div className="funil">{funil.map((f, i) => (
            <div key={i} className={`funil-row clickable ${drill === f.etapa_funil ? 'on' : ''}`} onClick={() => setDrill(drill === f.etapa_funil ? '' : f.etapa_funil)}>
              <span className="fs-lbl" style={{ width: 96 }}>{ETAPA_LABEL[f.etapa_funil] || f.etapa_funil}</span>
              <div className="fs-bar"><div className="fs-fill" style={{ width: `${Math.max(6, f.n / top * 100)}%`, background: 'linear-gradient(90deg,#7C5CFF,#31E1D6)' }}>{f.n.toLocaleString('es')}</div></div>
              {i > 0 && <span className="fs-drop" title="caída vs etapa anterior" style={{ color: f.caida > 50 ? 'var(--crit)' : f.caida > 30 ? 'var(--gold)' : 'var(--good)' }}>−{f.caida}%</span>}
            </div>
          ))}</div>
          {funil.length === 4 && <div className="ar-insight" style={{ marginTop: 10 }}>💡 Mayor fuga: <b>{fugaMax(funil)}</b>. La conversión global prospecto→matrícula es <b>{funil[3].conv_desde_inicio}%</b>.</div>}
        </div>

        {/* Conversión por segmento — switcher de dimensión */}
        <div className="glass c-half">
          <div className="hd"><span className="t">Conversión por segmento</span>
            <div className="seg">{DIMS.map(([k, l]) => <button key={k} className={dim === k ? 'on' : ''} onClick={() => setDim(k)}>{l}</button>)}</div></div>
          <table className="tbl"><thead><tr><th>{DIMS.find(d => d[0] === dim)?.[1]}</th><th>Postul.</th><th>Matríc.</th><th>Tasa real</th><th title="propensión media del modelo ML entre candidatos activos">Prop. IA</th></tr></thead>
            <tbody>{conv.slice(0, 10).map((c, i) => (
              <tr key={i}><td style={{ color: 'var(--txt)', fontSize: 11 }}>{c.segmento}</td><td>{c.postulantes}</td><td>{c.matriculas}</td>
                <td><span className={`pill ${c.tasa_matricula > 40 ? 'bajo' : c.tasa_matricula > 25 ? 'medio' : 'alto'}`}>{c.tasa_matricula}%</span></td>
                <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{c.propension_activos != null ? Math.round(c.propension_activos * 100) + '%' : '—'}</td></tr>
            ))}</tbody></table>
        </div>
      </div>

      {/* Drill-down: QUIÉNES están en la etapa seleccionada */}
      {drill && (
        <div className="glass c-full" style={{ marginTop: 14 }}>
          <div className="hd"><span className="t">{ETAPA_LABEL[drill]} — {gente ? gente.length : '…'} {gente && gente.length >= 60 ? '(top 60)' : ''}</span>
            <span className="b" style={{ cursor: 'pointer' }} onClick={() => setDrill('')}>✕ cerrar</span></div>
          {!gente ? <Loader t={t} /> : (
            <table className="tbl"><thead><tr><th>ID</th><th>Ciudad</th><th>País</th><th>Programa</th><th>Canal</th><th>Puntaje</th><th>Propensión</th></tr></thead>
              <tbody>{gente.slice(0, 60).map((p, i) => (
                <tr key={i}><td style={{ fontFamily: 'var(--mono)', fontSize: 10.5 }}>{p.appl_id}</td><td>{p.ciudad}</td><td style={{ fontSize: 11 }}>{p.pais_nombre}</td>
                  <td style={{ fontSize: 11 }}>{p.prog_nombre}</td><td style={{ fontSize: 11 }}>{p.canal}</td><td style={{ fontFamily: 'var(--mono)' }}>{p.puntaje_admision}</td>
                  <td>{p.etapa_funil === 'MATRICULÓ'
                    ? <span style={{ fontSize: 10.5, color: 'var(--good)' }}>✓ matriculado</span>
                    : p.propension != null
                      ? <span className="scorebadge" style={{ '--p': `${p.propension * 100}%` } as any}>{Math.round(p.propension * 100)}%</span>
                      : <span style={{ color: 'var(--txt-3)' }}>—</span>}</td></tr>
              ))}</tbody></table>
          )}
        </div>
      )}

      {/* Análisis NLP de carta de motivación */}
      <div className="glass c-full" style={{ marginTop: 14 }}>
        <div className="hd"><span className="t">{t('nlp_cand')}</span><span className="b">LLM-as-judge · AI Gateway</span></div>
        <textarea className="essay" value={essay} onChange={e => setEssay(e.target.value)} placeholder={t('nlp_ph')} />
        <button className="cta" onClick={analizar} disabled={busy} style={{ marginTop: 8 }}>{busy ? t('loading') : t('analizar')}</button>
        {nlp && <div className={`bub a${nlp.integridad === 'bloqueado_guardrail' ? ' warn' : ''}`} style={{ marginTop: 12, maxWidth: '100%' }}><Markdown text={nlp.analisis || ''} /></div>}
      </div></>
  )
}

// mayor caída entre etapas del embudo (para el insight)
function fugaMax(funil: any[]) {
  let worst = { et: '', caida: -1 }
  const LBL: any = { 'POSTULÓ': 'prospecto→postulación', ADMITIDO: 'postulación→admisión', 'MATRICULÓ': 'admisión→matrícula' }
  for (let i = 1; i < funil.length; i++) if (funil[i].caida > worst.caida) worst = { et: LBL[funil[i].etapa_funil] || funil[i].etapa_funil, caida: funil[i].caida }
  return `${worst.et} (−${worst.caida}%)`
}

// ============ CAMPUS — mapa LATAM + drill individual (3D + infra) ============
function Campus({ t }: any) {
  const [campus, setCampus] = useState<any[]>([])
  const [sel, setSel] = useState<string | null>(null)
  useEffect(() => { api.campus().then(r => setCampus(r.data || [])).catch(() => {}) }, [])
  if (sel) return <CampusDetail t={t} cid={sel} back={() => setSel(null)} />
  return (
    <><div className="eyebrow" style={{ marginTop: 26 }}>Presencia multi-país · América Latina</div>
      <h1 style={{ fontSize: 34 }}>{t('campus_t')}</h1>
      <div className="sub">{t('campus_sub')}</div>
      <div className="glass c-full" style={{ marginTop: 8, padding: 0, overflow: 'hidden' }}>
        <LatamMap campus={campus} metric="estudiantes" onCampusClick={(cid) => setSel(cid)} />
      </div>
      <div className="campusgrid">
        {campus.map((c, i) => (
          <div key={i} className="glass campuscard clickable" onClick={() => setSel(c.campus_id)}>
            <div className="cc-city">{c.ciudad} <span className="cc-flag">{c.pais}</span></div>
            <div className="cc-vert">{c.vertical}</div>
            <div className="cc-metrics"><span>{c.estudiantes} <small>alumnos</small></span><span>{Math.round(c.ocupacion_pct)}% <small>ocup.</small></span><span>${c.mensualidad_usd} <small>{c.moneda}</small></span></div>
            <div className="cc-go">{t('ver_campus')} →</div>
          </div>
        ))}
      </div></>
  )
}

function CampusDetail({ t, cid, back }: any) {
  const [d, setD] = useState<any>(null)
  useEffect(() => { setD(null); api.campusDetail(cid).then(setD).catch(() => setD({ error: 1 })) }, [cid])
  if (!d) return <div style={{ marginTop: 40 }}><Loader t={t} /></div>
  if (d.error) return <div style={{ marginTop: 40 }}>No encontrado. <a onClick={back} style={{ cursor: 'pointer', color: 'var(--violet-2)' }}>← volver</a></div>
  const c = d.campus
  const recs3d = d.infra.map((x: any) => ({ key: x.label, label: x.label, uso: x.uso, icon: x.icon }))
  const col = (e: string) => e === 'critico' ? 'var(--crit)' : e === 'ajustado' ? 'var(--gold)' : 'var(--good)'
  return (
    <><div className="eyebrow" style={{ marginTop: 26 }}><a onClick={back} style={{ cursor: 'pointer' }}>← {t('volver')}</a> · Campus 360</div>
      <h1 style={{ fontSize: 32 }}>Campus {c.ciudad}</h1>
      <div className="sub">{c.pais_nombre} · {c.vertical} · {c.estudiantes} alumnos · {d.en_riesgo} en riesgo alto</div>
      <div className="bento">
        <div className="glass c-half" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="hd" style={{ padding: '14px 18px' }}><span className="t">{t('gemelo_3d')}</span><span className="b">{c.ciudad}</span></div>
          <Campus3D recursos={recs3d} height={260} />
        </div>
        <div className="glass c-half">
          <div className="hd"><span className="t">{t('infra_campus')}</span><span className="b">demanda vs capacidad</span></div>
          <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {d.infra.map((x: any, i: number) => (
              <div key={i}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 5 }}>
                  <span>{x.icon} {x.label}</span><span style={{ color: col(x.estado), fontFamily: 'var(--mono)' }}>{x.uso}% · {x.demanda}/{x.capacidad} {x.unidad}</span></div>
                <div className="track"><div className="fill" style={{ width: `${Math.min(100, x.uso)}%`, background: col(x.estado), color: col(x.estado) }} /></div>
              </div>
            ))}
          </div>
        </div>
      </div></>
  )
}

// ============ DIGITAL TWIN ============
function DigitalTwin({ t }: any) {
  const [pct, setPct] = useState(0)
  const [fc, setFc] = useState(false)  // partir del forecast tendencial (opcional)
  const [sim, setSim] = useState<any>(null); const [busy, setBusy] = useState(false)
  const run = async (p: number, useFc: boolean) => { setBusy(true); try { setSim(await api.twinSim(p, useFc)) } finally { setBusy(false) } }
  useEffect(() => { run(pct, fc) }, [fc])  // 0% + sin forecast = estado actual real
  const REC = [['salas', '🏫'], ['energia', '⚡'], ['restaurante', '🍽'], ['laboratorios', '🔬'], ['dormitorios', '🛏']]
  const col = (e: string) => e === 'critico' ? 'var(--crit)' : e === 'ajustado' ? 'var(--gold)' : 'var(--good)'
  return (
    <><div className="eyebrow" style={{ marginTop: 26 }}>Digital Twin · simulación de escenarios</div>
      <div className="viewhd"><h1 style={{ fontSize: 34 }}>{t('twin_t')}</h1></div>
      <div className="glass" style={{ padding: '18px 22px', marginTop: 14 }}>
        <div className="hd"><span className="t">{t('escenario')}: {pct === 0 && !fc ? 'estado actual' : <>{t('crecimiento')} <b style={{ color: 'var(--violet-2)' }}>+{pct}%</b></>}</span>
          <label className="tw-toggle"><input type="checkbox" checked={fc} onChange={e => setFc(e.target.checked)} /> partir del forecast 2027</label></div>
        <input type="range" min="0" max="40" value={pct} onChange={e => setPct(+e.target.value)} onMouseUp={() => run(pct, fc)} onTouchEnd={() => run(pct, fc)} className="slider" />
        {pct === 0 && !fc && <div className="ar-insight" style={{ marginTop: 10 }}>💡 Mostrando la <b>ocupación actual</b> (sin crecimiento). Mueve el slider o activa el forecast para ver dónde se saturaría la infraestructura.</div>}
      </div>
      {busy && !sim ? <Loader t={t} /> : (
        <>
          <div className="glass c-full" style={{ marginTop: 14, padding: 0, overflow: 'hidden' }}>
            <LatamMap campus={(sim?.campus || []).map((c: any) => ({ ...c, ciudad: c.ciudad, estudiantes: c.matricula_sim, ocupacion_pct: c.recursos?.salas?.uso_pct, pais: c.pais }))} metric="uso" />
          </div>
          <div className="twinlist">
            {(sim?.campus || []).map((c: any, i: number) => (
              <div key={i} className="glass twincard">
                <div className="tc-hd"><b>{c.ciudad}</b><span>{c.matricula_base} → <b style={{ color: 'var(--violet-2)' }}>{c.matricula_sim}</b></span></div>
                <div className="tc-recs">{REC.map(([k, ic]) => {
                  const rr = c.recursos[k]; return (
                    <div key={k} className="tc-rec"><span className="tc-ic">{ic}</span>
                      <div className="tc-bar"><div className="tc-fill" style={{ width: `${Math.min(100, rr.uso_pct)}%`, background: col(rr.estado) }} /></div>
                      <span className="tc-pct" style={{ color: col(rr.estado) }}>{rr.uso_pct}%</span></div>
                  )
                })}</div>
              </div>
            ))}
          </div>
        </>
      )}</>
  )
}

// ============ INVESTIGACIÓN — GraphRAG + papers con visor PDF inline ============
function GraphExplorer({ t, lang }: any) {
  const [graph, setGraph] = useState<any>(null)
  const [q, setQ] = useState(''); const [ans, setAns] = useState<any>(null); const [busy, setBusy] = useState(false)
  const [papers, setPapers] = useState<any[]>([]); const [pdf, setPdf] = useState<any>(null)
  useEffect(() => { api.graph().then(setGraph).catch(() => {}); api.papers().then(setPapers).catch(() => {}) }, [])
  const ask = async () => {
    if (!q.trim()) return; setBusy(true)
    try { const [a] = await Promise.all([api.ask(q, lang)]); setAns(a); api.papers(q).then(setPapers).catch(() => {}) } finally { setBusy(false) }
  }
  return (
    <><div className="eyebrow" style={{ marginTop: 26 }}>Investigación · GraphRAG + biblioteca de papers</div>
      <h1 style={{ fontSize: 34 }}>{t('explorer_t')}</h1>
      <div className="chatin" style={{ maxWidth: 620, marginTop: 6 }}>
        <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask()} placeholder={t('explorer_ph')} />
        <button onClick={ask}>{busy ? '…' : '→'}</button>
      </div>
      {ans && <div className="glass" style={{ padding: '14px 18px', marginTop: 12 }}><div className="bub a" style={{ maxWidth: '100%' }}><Markdown text={ans.respuesta} />{ans.fuentes?.length ? <span className="src">{ans.fuentes.map((f: any) => `[${f.chunk_id}]`).join(' · ')}</span> : null}</div></div>}
      <div className="bento">
        <div className="glass c-half" style={{ padding: 0, overflow: 'hidden', minHeight: 420 }}>
          <div className="hd" style={{ padding: '14px 18px' }}><span className="t">{t('grafo_conoc')}</span></div>
          <KnowledgeGraph data={graph} height={380} interactive />
        </div>
        <div className="glass c-half">
          <div className="hd"><span className="t">{t('papers_rel')}</span><span className="b">{papers.length}</span></div>
          <div className="paperlist">
            {papers.map((p, i) => (
              <div key={i} className="paperitem" onClick={() => setPdf(p)}>
                <div className="pp-t">{p.titulo}</div>
                <div className="pp-m">{p.autores} · {p.anio} · {p.citas} citas</div>
              </div>
            ))}
          </div>
        </div>
      </div>
      {pdf && (
        <div className="pdfmodal" onClick={() => setPdf(null)}>
          <div className="pdfbox" onClick={e => e.stopPropagation()}>
            <div className="pdfhd"><div><b>{pdf.titulo}</b><div className="pp-m">{pdf.autores} · {pdf.anio}</div></div><button onClick={() => setPdf(null)}>✕</button></div>
            <iframe src={api.paperPdfUrl(pdf.paper_id)} title="pdf" className="pdfframe" />
          </div>
        </div>
      )}</>
  )
}

// ============ GENIE Agent Mode ============
function GenieView({ t }: any) {
  const [q, setQ] = useState(''); const [res, setRes] = useState<any>(null); const [busy, setBusy] = useState(false)
  const ask = async () => { if (!q.trim()) return; setBusy(true); try { setRes(await api.genieAsk(q)) } finally { setBusy(false) } }
  return (
    <><div className="eyebrow" style={{ marginTop: 26 }}>Genie · Agent Mode (investigación multi-paso)</div>
      <h1 style={{ fontSize: 34 }}>{t('genie_t')}</h1>
      <div className="glass c-full" style={{ marginTop: 16, minHeight: 240 }}>
        <div className="chatin" style={{ marginTop: 0 }}><input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask()} placeholder={t('genie_ph')} /><button onClick={ask}>→</button></div>
        <div style={{ marginTop: 16 }}>{busy ? <Loader t={t} /> : res ? (
          <div>
            {/* pasos de razonamiento del agente */}
            {res.pasos?.length ? <div className="genie-steps">{res.pasos.map((p: string, i: number) => <div key={i} className="genie-step"><span className="gs-n">{i + 1}</span>{p}</div>)}</div> : null}
            <div className="bub a" style={{ maxWidth: '100%' }}><Markdown text={res.texto || res.error || ''} /></div>
            {/* consultas SQL que respaldan el análisis */}
            {res.queries?.length ? <details className="genie-sql"><summary>{res.queries.length} {t('genie_consultas')}</summary>{res.queries.map((sq: string, i: number) => <pre key={i} className="genie-q">{sq}</pre>)}</details> : (res.sql ? <span className="src">SQL: {res.sql.slice(0, 140)}</span> : null)}
          </div>
        ) : <div style={{ color: 'var(--txt-3)', fontFamily: 'var(--mono)', fontSize: 12 }}>{t('genie_hint')}</div>}</div>
      </div></>
  )
}
