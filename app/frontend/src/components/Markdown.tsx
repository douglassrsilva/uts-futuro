// Renderizador Markdown con react-markdown + remark-gfm (tablas, listas ordenadas, ---, etc.).
// Sustituye al parser casero anterior (que rompía en listas numeradas y separadores). Mapeamos
// los elementos a las clases CSS del design system (mdh/mdtable/mdul/…) vía `components`.
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Limpia las citas que devuelve Genie (\[[1](url)\], [[2](url)]) → superíndice discreto [1].
function limpiarCitas(s: string) {
  return (s || '')
    .replace(/\\?\[\[(\d+)\]\([^)]*\)\\?\]/g, ' [$1]')
    .replace(/\[\[(\d+)\]\([^)]*\)\]/g, ' [$1]')
}

const comps: any = {
  h1: (p: any) => <div className="mdh mdh1" {...p} />,
  h2: (p: any) => <div className="mdh mdh2" {...p} />,
  h3: (p: any) => <div className="mdh mdh3" {...p} />,
  h4: (p: any) => <div className="mdh mdh3" {...p} />,
  p: (p: any) => <p className="mdp" {...p} />,
  ul: (p: any) => <ul className="mdul" {...p} />,
  ol: (p: any) => <ol className="mdol" {...p} />,
  code: (p: any) => <code className="mdcode" {...p} />,
  table: (p: any) => <table className="mdtable" {...p} />,
  a: ({ node, ...p }: any) => <a className="mdlink" target="_blank" rel="noreferrer" {...p} />,
  hr: () => <hr className="mdhr" />,
}

export function Markdown({ text }: { text: string }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={comps}>
        {limpiarCitas(text)}
      </ReactMarkdown>
    </div>
  )
}
