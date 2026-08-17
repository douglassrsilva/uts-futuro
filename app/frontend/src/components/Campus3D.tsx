import { useEffect, useRef } from 'react'
import * as THREE from 'three'

// Mini-campus 3D esquemático: cada edificio = un recurso; altura = capacidad,
// color = nivel de uso (verde/ámbar/rojo). Rota suavemente. WebGL (Three.js).
interface Rec { key: string; label: string; uso: number; icon: string }
export function Campus3D({ recursos, height = 260 }: { recursos: Rec[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const W = ref.current.clientWidth, H = height
    const scene = new THREE.Scene()
    const cam = new THREE.PerspectiveCamera(45, W / H, 0.1, 100)
    cam.position.set(0, 7, 11); cam.lookAt(0, 1, 0)
    const rend = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    rend.setSize(W, H); rend.setPixelRatio(Math.min(2, devicePixelRatio))
    ref.current.appendChild(rend.domElement)
    scene.add(new THREE.AmbientLight(0xffffff, 0.65))
    const dir = new THREE.DirectionalLight(0xffffff, 0.9); dir.position.set(5, 10, 7); scene.add(dir)
    const pt = new THREE.PointLight(0x7C5CFF, 0.6, 30); pt.position.set(-4, 6, 4); scene.add(pt)
    // base plate
    const base = new THREE.Mesh(new THREE.BoxGeometry(10, 0.3, 10), new THREE.MeshStandardMaterial({ color: 0x14121f, roughness: .9 }))
    base.position.y = -0.15; scene.add(base)
    // grid lines
    const grid = new THREE.GridHelper(10, 10, 0x2a2740, 0x201d33); grid.position.y = 0.02; scene.add(grid)
    const col = (u: number) => u > 100 ? 0xFF6B7A : u > 85 ? 0xF5C86B : 0x3BE0A0
    const n = recursos.length
    const buildings: THREE.Mesh[] = []
    recursos.forEach((r, i) => {
      const h = Math.max(0.6, Math.min(5, r.uso / 22))
      const g = new THREE.BoxGeometry(1.3, h, 1.3)
      const mat = new THREE.MeshStandardMaterial({ color: col(r.uso), emissive: col(r.uso), emissiveIntensity: .28, roughness: .5, metalness: .2 })
      const m = new THREE.Mesh(g, mat)
      const ang = (i / n) * Math.PI * 2
      m.position.set(Math.cos(ang) * 3, h / 2, Math.sin(ang) * 3)
      scene.add(m); buildings.push(m)
      // "halo" ring on floor
      const ring = new THREE.Mesh(new THREE.RingGeometry(0.95, 1.05, 24), new THREE.MeshBasicMaterial({ color: col(r.uso), side: THREE.DoubleSide, transparent: true, opacity: .5 }))
      ring.rotation.x = -Math.PI / 2; ring.position.set(m.position.x, 0.03, m.position.z); scene.add(ring)
    })
    let raf = 0, t = 0
    const loop = () => { t += 0.004; scene.rotation.y = t; buildings.forEach((b, i) => { b.scale.y = 1 + Math.sin(t * 3 + i) * 0.02 }); rend.render(scene, cam); raf = requestAnimationFrame(loop) }
    loop()
    return () => { cancelAnimationFrame(raf); rend.dispose(); ref.current && (ref.current.innerHTML = '') }
  }, [recursos, height])
  return <div ref={ref} style={{ width: '100%', height }} />
}
