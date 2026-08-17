// Logo U-Grafo (animado en loading) + Loader — compartido entre App y componentes.
export function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg className="ug" width={size} height={size} viewBox="0 0 52 52">
      <defs><linearGradient id="uggrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#7C5CFF" /><stop offset="1" stopColor="#31E1D6" /></linearGradient></defs>
      <rect x="1" y="1" width="50" height="50" rx="14" fill="#0C0C14" stroke="url(#uggrad)" strokeWidth="1.3" />
      <path className="edge" d="M16 15 L16 30 Q16 38 26 38 Q36 38 36 30 L36 15" />
      <circle className="n1 kgnode" cx="16" cy="15" r="3" fill="#9C84FF" /><circle className="n2 kgnode" cx="36" cy="15" r="3" fill="#31E1D6" /><circle className="n3 kgnode" cx="26" cy="38" r="3.2" fill="#F5C86B" />
    </svg>
  )
}
export function Loader({ t }: any) { return <div className="loading loadwrap"><Logo size={44} /><span>{t ? t('loading') : 'cargando…'}</span></div> }
