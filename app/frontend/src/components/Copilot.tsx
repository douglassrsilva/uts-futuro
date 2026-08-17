import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import { Logo, Loader } from '../shared'
import { Markdown } from './Markdown'

// Renderiza el resultado de cada herramienta que el agente invocó (inline).
function Render({ r, goStudent }: { r: any; goStudent: (id: string) => void }) {
  if (r.tipo === 'tabla_riesgo') return (
    <div className="rnd">
      <div className="rnd-t">◆ {r.rows.length} alumnos en riesgo</div>
      <table className="tbl"><thead><tr><th>Alumno</th><th>Campus</th><th>Riesgo</th><th>Factor</th><th></th></tr></thead>
        <tbody>{r.rows.slice(0, 8).map((x: any, i: number) => (
          <tr key={i} className="clickrow" onClick={() => goStudent(x.student_master_id)}>
            <td style={{ color: 'var(--txt)' }}>{x.nombre}</td><td>{x.ciudad}</td>
            <td><span className="scorebadge" style={{ '--p': `${x.riesgo_score * 100}%` } as any}>{Math.round(x.riesgo_score * 100)}%</span></td>
            <td><span className="pill alto">{x.factor_principal}</span></td><td className="ar-go">→</td></tr>
        ))}</tbody></table>
    </div>)
  if (r.tipo === 'ficha360') { const p = r.data.perfil, ri = r.data.riesgo || {}; return (
    <div className="rnd" onClick={() => goStudent(p.student_master_id)} style={{ cursor: 'pointer' }}>
      <div className="rnd-t">🎓 {p.nombre} · {p.program_name} · {p.ciudad}</div>
      <div className="rnd-chips"><span>GPA {p.gpa}</span><span>Sem {p.semestre}</span><span style={{ color: 'var(--crit)' }}>Riesgo {Math.round((ri.riesgo_score || 0) * 100)}%</span><span>{ri.factor_principal}</span></div>
      <div className="rnd-accion">→ {r.data.accion_recomendada}</div>
    </div>)
  }
  if (r.tipo === 'metrica') { const mx = Math.max(...r.rows.map((x: any) => x.valor), 0.01); return (
    <div className="rnd"><div className="rnd-t">📊 {r.titulo}</div>
      {r.rows.map((x: any, i: number) => (<div className="occrow" key={i}><div className="cn">{x[r.dim]}</div>
        <div className="track"><div className="fill" style={{ width: `${x.valor / mx * 100}%`, background: 'var(--violet)', color: 'var(--violet)' }} /></div>
        <div className="p">{x.valor}</div></div>))}</div>)
  }
  if (r.tipo === 'digitaltwin') { const cr = r.data.campus.filter((c: any) => Object.values(c.recursos).some((v: any) => v.estado === 'critico')); return (
    <div className="rnd"><div className="rnd-t">🏛 Simulación +{r.data.crecimiento_pct}% matrícula</div>
      {cr.length ? <div className="rnd-alert">⚠ Capacidad crítica en: {cr.map((c: any) => c.ciudad).join(', ')}</div> : <div className="rnd-accion">Sin déficit de capacidad.</div>}
      <div className="rnd-chips">{r.data.campus.slice(0, 4).map((c: any, i: number) => <span key={i}>{c.ciudad}: {c.recursos.salas.uso_pct}% salas</span>)}</div></div>)
  }
  if (r.tipo === 'admisiones') return (
    <div className="rnd"><div className="rnd-t">🎯 Funil de captación</div>
      <div className="rnd-chips">{r.funil.map((f: any, i: number) => <span key={i}>{f.etapa_funil}: {f.n}</span>)}</div>
      {r.yield?.[0] && <div className="rnd-accion">Mejor canal: <b>{r.yield[0].canal}</b> ({Math.round(r.yield[0].yield_rate * 100)}% yield)</div>}</div>)
  if (r.tipo === 'conocimiento') return (
    <div className="rnd"><div className="rnd-t">🔎 {r.tema}</div>
      {r.docs.map((d: any, i: number) => <div key={i} className="rnd-doc"><b>{d.titulo}</b> <span>[{d.chunk_id}]</span></div>)}</div>)
  return null
}

export function Copilot({ t, lang, goStudent }: any) {
  const [msgs, setMsgs] = useState<any[]>([])
  const [q, setQ] = useState(''); const [busy, setBusy] = useState(false)
  const [sug, setSug] = useState<string[]>([])
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { api.sugerencias(lang).then(s => setSug(s.items)).catch(() => {}) }, [lang])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])

  const send = async (text?: string) => {
    const mensaje = (text ?? q).trim(); if (!mensaje || busy) return
    setQ(''); const hist = msgs.map(m => ({ role: m.role === 'u' ? 'user' : 'assistant', content: m.text || '' }))
    setMsgs(m => [...m, { role: 'u', text: mensaje }]); setBusy(true)
    try { const r = await api.agente(mensaje, lang, hist); setMsgs(m => [...m, { role: 'a', text: r.respuesta, renders: r.renders || [] }]) }
    catch { setMsgs(m => [...m, { role: 'a', text: '(error del copiloto)' }]) } finally { setBusy(false) }
  }

  return (
    <div className="copilot">
      {msgs.length === 0 ? (
        <div className="cop-hero">
          <div className="eyebrow">Copiloto institucional · agente</div>
          <h1>{t('cop_h1a')} <span className="g">{t('cop_h1b')}</span></h1>
          <p className="cop-lead">{t('cop_lead')}</p>
          <div className="cop-sug">{sug.map((s, i) => <button key={i} className="sugchip" onClick={() => send(s)}>{s} <span>↗</span></button>)}</div>
        </div>
      ) : (
        <div className="cop-thread">
          {msgs.map((m, i) => (
            <div key={i} className={`cop-msg ${m.role}`}>
              {m.role === 'a' && <div className="cop-av"><Logo size={22} /></div>}
              <div className="cop-body">
                <div className={`bub ${m.role}`}>{m.role === 'a' ? <Markdown text={m.text} /> : m.text}</div>
                {m.renders?.map((r: any, j: number) => <Render key={j} r={r} goStudent={goStudent} />)}
              </div>
            </div>
          ))}
          {busy && <div className="cop-msg a"><div className="cop-av"><Logo size={22} /></div><div className="loading loadwrap" style={{ padding: 14 }}><Logo size={30} /><span>{t('cop_pensando')}</span></div></div>}
          <div ref={endRef} />
        </div>
      )}
      <div className="cop-inputbar">
        <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} placeholder={t('cop_ph')} />
        <button onClick={() => send()} disabled={busy}>{busy ? '…' : '↑'}</button>
      </div>
    </div>
  )
}
