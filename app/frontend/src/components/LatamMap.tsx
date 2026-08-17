import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

// Mapa LATAM. Los campus se pintan como una CAPA NATIVA de círculos (GeoJSON + circle layer),
// no como marcadores DOM: la capa posiciona cada punto exactamente por [lon,lat] sin medir el
// DOM (los marcadores HTML animados se anclaban mal y desplazaban los puntos al océano).
// onCampusClick: click en un punto → abre la maqueta 3D (CampusDetail).
export function LatamMap({ campus, metric = 'estudiantes', onCampusClick }:
  { campus: any[]; metric?: string; onCampusClick?: (campusId: string) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const ready = useRef(false)
  const clickCb = useRef(onCampusClick)
  clickCb.current = onCampusClick

  const col = (v: number) => v > 90 ? '#FF6B7A' : v > 75 ? '#F5C86B' : '#31E1D6'

  const toGeoJSON = (rows: any[]): any => ({
    type: 'FeatureCollection',
    features: (rows || [])
      .filter(c => c.lat != null && c.lon != null)
      .map(c => {
        const uso = c.ocupacion_pct ?? 60
        return {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [Number(c.lon), Number(c.lat)] },
          properties: {
            campus_id: c.campus_id,
            color: col(uso),
            radius: 6 + Math.min(14, (c.estudiantes || 100) / 90),
            label: `${c.ciudad || c.campus_id} · ${c.pais || ''}`,
            detail: `${c.estudiantes || '—'} alumnos · ${Math.round(uso)}% ${metric === 'uso' ? 'uso salas' : 'ocup.'}`,
            vertical: c.vertical || '',
          },
        }
      }),
  })

  useEffect(() => {
    if (map.current || !ref.current) return
    const m = new maplibregl.Map({
      container: ref.current,
      style: {
        version: 8,
        sources: { carto: { type: 'raster', tiles: ['https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© CARTO' } },
        layers: [{ id: 'carto', type: 'raster', source: 'carto' }],
      },
      center: [-63, -17], zoom: 2.4, attributionControl: false,
    })
    map.current = m
    const popup = new maplibregl.Popup({ offset: 12, closeButton: false, closeOnMove: false })

    m.on('load', () => {
      m.addSource('campus', { type: 'geojson', data: toGeoJSON(campus) })
      // halo suave (círculo grande translúcido) + punto central nítido
      m.addLayer({
        id: 'campus-halo', type: 'circle', source: 'campus',
        paint: {
          'circle-radius': ['*', ['get', 'radius'], 2.1],
          'circle-color': ['get', 'color'], 'circle-opacity': 0.18, 'circle-blur': 0.6,
        },
      })
      m.addLayer({
        id: 'campus-dot', type: 'circle', source: 'campus',
        paint: {
          'circle-radius': ['get', 'radius'], 'circle-color': ['get', 'color'],
          'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff', 'circle-opacity': 0.95,
        },
      })
      const clickable = !!clickCb.current
      m.on('mouseenter', 'campus-dot', (e: any) => {
        m.getCanvas().style.cursor = clickable ? 'pointer' : ''
        const f = e.features?.[0]; if (!f) return
        const [lon, lat] = f.geometry.coordinates
        const hint = clickable ? '<br><small style="color:#7C5CFF">▸ ver maqueta 3D</small>' : ''
        const v = f.properties.vertical ? `<br><small>${f.properties.vertical}</small>` : ''
        popup.setLngLat([lon, lat]).setHTML(
          `<div style="font-family:Inter,sans-serif;color:#111"><b>${f.properties.label}</b><br>${f.properties.detail}${v}${hint}</div>`
        ).addTo(m)
      })
      m.on('mouseleave', 'campus-dot', () => { m.getCanvas().style.cursor = ''; popup.remove() })
      m.on('click', 'campus-dot', (e: any) => {
        const f = e.features?.[0]
        if (f && clickCb.current) clickCb.current(f.properties.campus_id)
      })
      ready.current = true
    })
  }, [])

  // actualizar los datos de la capa cuando cambian los campus (sin recrear el mapa)
  useEffect(() => {
    const m = map.current
    if (!m) return
    const apply = () => {
      const src = m.getSource('campus') as maplibregl.GeoJSONSource | undefined
      if (src) src.setData(toGeoJSON(campus))
    }
    if (ready.current) apply(); else m.once('idle', apply)
  }, [campus, metric])

  return <div ref={ref} style={{ width: '100%', height: 420 }} />
}
