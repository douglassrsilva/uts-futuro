import { useEffect, useRef, useState } from 'react'

interface N { node_id: string; node_type: string; label: string; x: number; y: number; vx: number; vy: number }
interface E { src_id: string; dst_id: string; rel_type: string; weight?: number }
const COLOR: Record<string, string> = { Curso: '#31E1D6', Programa: '#9C84FF', 'Área': '#F5C86B' }

export function KnowledgeGraph({ data, height = 300, interactive = false }: { data: { nodes: any[]; edges: any[] } | null; height?: number; interactive?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const wrap = useRef<HTMLDivElement>(null)
  const [sel, setSel] = useState<N | null>(null)
  const [search, setSearch] = useState('')
  // refs leídos DENTRO del loop de render: cambiar selección/búsqueda NO re-inicializa el layout
  // (ese era el bug del "salto abrupto": sel/search estaban en las deps del useEffect y re-random-
  // izaban todas las posiciones en cada clic/tecla).
  const selRef = useRef<string | null>(null)
  const searchRef = useRef('')
  const st = useRef<any>({ nodes: [], idmap: {}, edges: [], deg: {}, drag: null, raf: 0, W: 0, H: height })

  useEffect(() => { selRef.current = sel?.node_id || null }, [sel])
  useEffect(() => { searchRef.current = search }, [search])

  // Inicialización + simulación: SÓLO depende de data/height/interactive (no de sel/search).
  useEffect(() => {
    if (!data?.nodes?.length || !ref.current) return
    const cv = ref.current, ctx = cv.getContext('2d')!
    const W = wrap.current!.clientWidth, H = height
    cv.width = W * devicePixelRatio; cv.height = H * devicePixelRatio; ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0)
    const s = st.current; s.W = W; s.H = H
    const cx = W / 2, cy = H / 2
    const idmap: Record<string, N> = {}
    // reparto inicial en espiral/anillo ancho, cubriendo el área (no un anillo fino en el borde)
    const list = data.nodes.slice(0, interactive ? 120 : 40)
    s.nodes = list.map((n: any, i: number) => {
      const a = i * 2.399963  // ángulo áureo → reparto uniforme
      const rr = Math.sqrt(i / list.length) * Math.min(W, H) * 0.42
      const node: N = { ...n, x: cx + Math.cos(a) * rr, y: cy + Math.sin(a) * rr, vx: 0, vy: 0 }
      idmap[n.node_id] = node; return node
    })
    s.idmap = idmap
    s.edges = data.edges.filter((e: E) => idmap[e.src_id] && idmap[e.dst_id])
    s.deg = {}; s.edges.forEach((e: E) => { s.deg[e.src_id] = (s.deg[e.src_id] || 0) + 1; s.deg[e.dst_id] = (s.deg[e.dst_id] || 0) + 1 })

    let cool = 0
    const loop = () => {
      const settling = cool < 320
      if (settling || s.drag) {
        const damp = 0.9
        // repulsión (moderada + con distancia mínima para no explotar) — O(n²)
        for (const a of s.nodes) {
          let fx = 0, fy = 0
          for (const b of s.nodes) {
            if (a === b) continue
            const dx = a.x - b.x, dy = a.y - b.y
            const d2 = Math.max(dx * dx + dy * dy, 25)
            const f = 620 / d2
            fx += dx * f; fy += dy * f
          }
          // gravedad al centro FUERTE (impide que se peguen a los bordes)
          fx += (cx - a.x) * 0.03; fy += (cy - a.y) * 0.03
          a.vx = (a.vx + fx) * damp; a.vy = (a.vy + fy) * damp
        }
        // resortes de las aristas (longitud de reposo 70)
        for (const e of s.edges) {
          const a = idmap[e.src_id], b = idmap[e.dst_id]
          const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1, f = (d - 70) * 0.02
          a.vx += dx / d * f; a.vy += dy / d * f; b.vx -= dx / d * f; b.vy -= dy / d * f
        }
        for (const a of s.nodes) {
          if (s.drag === a) continue
          a.x += Math.max(-6, Math.min(6, a.vx)); a.y += Math.max(-6, Math.min(6, a.vy))
          // frontera SUAVE: si se pasa del margen, empuje de vuelta (sin clavarlo a la pared)
          const m = 20
          if (a.x < m) a.vx += (m - a.x) * 0.4; else if (a.x > W - m) a.vx -= (a.x - (W - m)) * 0.4
          if (a.y < m) a.vy += (m - a.y) * 0.4; else if (a.y > H - m) a.vy -= (a.y - (H - m)) * 0.4
        }
        cool++
      }
      // ---- dibujo ----
      const q = selRef.current
      const qr = searchRef.current.trim().toLowerCase()
      ctx.clearRect(0, 0, W, H); ctx.lineWidth = 1
      for (const e of s.edges) {
        const a = idmap[e.src_id], b = idmap[e.dst_id]
        const on = q && (a.node_id === q || b.node_id === q)
        if (qr && !on) { ctx.globalAlpha = 0.08 } else { ctx.globalAlpha = 1 }
        const g = ctx.createLinearGradient(a.x, a.y, b.x, b.y)
        g.addColorStop(0, on ? 'rgba(245,200,107,0.85)' : 'rgba(124,92,255,0.35)')
        g.addColorStop(1, on ? 'rgba(245,200,107,0.4)' : 'rgba(49,225,214,0.12)')
        ctx.strokeStyle = g; ctx.lineWidth = on ? 2 : 1; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke()
      }
      ctx.globalAlpha = 1
      for (const n of s.nodes) {
        const r = 4 + Math.min(8, (s.deg[n.node_id] || 0) * 1.1)
        const match = qr ? (n.label?.toLowerCase().includes(qr)) : false
        // con búsqueda activa: los que NO coinciden se atenúan mucho (FILTRO visual real)
        const dim = (qr && !match) || (q && q !== n.node_id && !qr)
        ctx.globalAlpha = dim ? 0.15 : 1
        ctx.beginPath(); ctx.arc(n.x, n.y, match ? r + 3 : r, 0, 7); ctx.fillStyle = COLOR[n.node_type] || '#9C84FF'
        ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = match ? 18 : 8; ctx.fill(); ctx.shadowBlur = 0
        // etiqueta: nodo seleccionado, coincidencias de búsqueda, o nodos muy conectados
        if (interactive && !dim && (q === n.node_id || match || r > 8.5)) {
          ctx.fillStyle = '#F4F3FA'; ctx.font = '11px Inter,sans-serif'
          ctx.fillText((n.label || '').slice(0, 24), n.x + r + 4, n.y + 3)
        }
        ctx.globalAlpha = 1
      }
      s.raf = requestAnimationFrame(loop)
    }
    cancelAnimationFrame(s.raf); loop()
    return () => cancelAnimationFrame(s.raf)
  }, [data, height, interactive])

  // al escribir en la búsqueda, "recalentar" un poco la simulación no es necesario — el layout
  // es estable; sólo cambia el resaltado. Pero re-despertamos si el usuario arrastra.
  const at = (ev: React.MouseEvent) => { const s = st.current, rc = ref.current!.getBoundingClientRect(); const mx = ev.clientX - rc.left, my = ev.clientY - rc.top; return s.nodes.find((n: N) => (n.x - mx) ** 2 + (n.y - my) ** 2 < 200) || null }

  return (
    <div ref={wrap} style={{ position: 'relative', width: '100%', height }}>
      {interactive && (
        <div style={{ position: 'absolute', top: 12, left: 12, zIndex: 3 }}>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="🔎 buscar por nombre…"
            style={{ background: 'rgba(12,12,20,.9)', border: '1px solid var(--stroke)', borderRadius: 9, padding: '8px 12px', fontSize: 12, color: 'var(--txt)', fontFamily: 'var(--sans)', width: 210 }} />
        </div>
      )}
      <canvas ref={ref} style={{ width: '100%', height, cursor: interactive ? 'grab' : 'default' }}
        onMouseDown={interactive ? e => { st.current.drag = at(e) } : undefined}
        onMouseMove={interactive ? e => { const s = st.current; if (s.drag) { const rc = ref.current!.getBoundingClientRect(); s.drag.x = e.clientX - rc.left; s.drag.y = e.clientY - rc.top; s.drag.vx = 0; s.drag.vy = 0 } } : undefined}
        onMouseUp={interactive ? () => { st.current.drag = null } : undefined}
        onMouseLeave={interactive ? () => { st.current.drag = null } : undefined}
        onClick={interactive ? e => { const n = at(e); setSel(n) } : undefined} />
      {interactive && sel && (
        <div style={{ position: 'absolute', top: 12, right: 12, background: 'rgba(12,12,20,.92)', border: '1px solid var(--stroke)', borderRadius: 10, padding: '10px 14px', fontSize: 12, maxWidth: 220 }}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--txt-3)', textTransform: 'uppercase' }}>{sel.node_type}</div>
          <div style={{ fontWeight: 600, marginTop: 2 }}>{sel.label}</div>
          <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 4 }}>{st.current.deg[sel.node_id] || 0} conexiones</div>
        </div>
      )}
    </div>
  )
}
