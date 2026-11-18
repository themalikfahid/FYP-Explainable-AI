import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Float, MeshDistortMaterial, Sparkles } from "@react-three/drei";
import * as THREE from "three";

/** Deterministic pseudo-random so scenes look the same on every load. */
function rng(seed: number) { let s = seed; return () => (s = (s * 16807) % 2147483647) / 2147483647; }

function heartShape(): THREE.Shape {
  const s = new THREE.Shape();
  s.moveTo(0, -1.15);
  s.bezierCurveTo(-0.2, -0.95, -1.5, -0.3, -1.5, 0.55);
  s.bezierCurveTo(-1.5, 1.2, -0.95, 1.55, -0.45, 1.55);
  s.bezierCurveTo(-0.15, 1.55, 0, 1.3, 0, 1.05);
  s.bezierCurveTo(0, 1.3, 0.15, 1.55, 0.45, 1.55);
  s.bezierCurveTo(0.95, 1.55, 1.5, 1.2, 1.5, 0.55);
  s.bezierCurveTo(1.5, -0.3, 0.2, -0.95, 0, -1.15);
  return s;
}

export function Heart({ color = "#ff4d73", emissive = "#8b1238", pulse = true }: { color?: string; emissive?: string; pulse?: boolean }) {
  const group = useRef<THREE.Group>(null!);
  const geo = useMemo(() => {
    const g = new THREE.ExtrudeGeometry(heartShape(), { depth: 0.9, bevelEnabled: true, bevelThickness: 0.45, bevelSize: 0.4, bevelSegments: 14, curveSegments: 40 });
    g.center();
    return g;
  }, []);
  useFrame(({ clock }) => {
    if (!pulse) return;
    const t = clock.elapsedTime;
    const beat = Math.pow(Math.max(0, Math.sin(t * 2.6)), 8) * 0.07 + Math.pow(Math.max(0, Math.sin(t * 2.6 - 0.7)), 8) * 0.035;
    group.current.scale.setScalar(1 + beat);
  });
  return (
    <group ref={group}>
      <mesh geometry={geo} castShadow>
        <meshPhysicalMaterial color={color} emissive={emissive} emissiveIntensity={0.9} metalness={0.25} roughness={0.22} clearcoat={1} clearcoatRoughness={0.15} />
      </mesh>
      <mesh geometry={geo} scale={1.08}>
        <meshBasicMaterial color="#22d3ee" wireframe transparent opacity={0.12} />
      </mesh>
    </group>
  );
}

export function Rings() {
  const a = useRef<THREE.Mesh>(null!), b = useRef<THREE.Mesh>(null!), c = useRef<THREE.Mesh>(null!);
  useFrame((_, d) => {
    a.current.rotation.z += d * 0.25; b.current.rotation.z -= d * 0.18; c.current.rotation.z += d * 0.12;
  });
  return (
    <group rotation={[Math.PI / 2.6, 0.3, 0]}>
      <mesh ref={a}><torusGeometry args={[2.9, 0.012, 16, 160]} /><meshBasicMaterial color="#22d3ee" transparent opacity={0.65} /></mesh>
      <mesh ref={b} rotation={[0.25, 0, 0]}><torusGeometry args={[3.35, 0.01, 16, 160]} /><meshBasicMaterial color="#7c83ff" transparent opacity={0.55} /></mesh>
      <mesh ref={c} rotation={[-0.2, 0, 0]}><torusGeometry args={[3.8, 0.008, 16, 160]} /><meshBasicMaterial color="#a78bfa" transparent opacity={0.4} /></mesh>
    </group>
  );
}

/** Neural-network style cloud: nodes on a sphere shell joined by nearby-edge lines. */
export function Network({ count = 46, radius = 3.2, seed = 7, spin = 0.05 }: { count?: number; radius?: number; seed?: number; spin?: number }) {
  const group = useRef<THREE.Group>(null!);
  const { points, lines } = useMemo(() => {
    const r = rng(seed);
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i < count; i++) {
      const u = r() * 2 - 1, t = r() * Math.PI * 2, k = Math.sqrt(1 - u * u), rad = radius * (0.75 + r() * 0.35);
      pts.push(new THREE.Vector3(k * Math.cos(t) * rad, u * rad, k * Math.sin(t) * rad));
    }
    const seg: number[] = [];
    pts.forEach((p, i) => {
      pts.map((q, j) => ({ j, d: p.distanceTo(q) })).filter((o) => o.j > i).sort((a, b) => a.d - b.d).slice(0, 2).forEach((o) => {
        const q = pts[o.j]; seg.push(p.x, p.y, p.z, q.x, q.y, q.z);
      });
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(seg, 3));
    return { points: pts, lines: g };
  }, [count, radius, seed]);
  useFrame((_, d) => { group.current.rotation.y += d * spin; group.current.rotation.x += d * spin * 0.3; });
  return (
    <group ref={group}>
      <lineSegments geometry={lines}><lineBasicMaterial color="#5b8def" transparent opacity={0.28} /></lineSegments>
      {points.map((p, i) => (
        <mesh key={i} position={p}><sphereGeometry args={[i % 5 === 0 ? 0.075 : 0.045, 12, 12]} /><meshBasicMaterial color={i % 5 === 0 ? "#22d3ee" : "#a5b4fc"} /></mesh>
      ))}
    </group>
  );
}

export function Lights() {
  return (
    <>
      <ambientLight intensity={0.55} />
      <pointLight position={[4, 3, 5]} intensity={42} color="#22d3ee" />
      <pointLight position={[-5, -2, 4]} intensity={36} color="#7c83ff" />
      <pointLight position={[0, 4, -3]} intensity={28} color="#ff4d73" />
    </>
  );
}

export function Pointer({ children, strength = 0.35 }: { children: React.ReactNode; strength?: number }) {
  const g = useRef<THREE.Group>(null!);
  useFrame(({ pointer }) => {
    g.current.rotation.y = THREE.MathUtils.lerp(g.current.rotation.y, pointer.x * strength, 0.05);
    g.current.rotation.x = THREE.MathUtils.lerp(g.current.rotation.x, -pointer.y * strength * 0.6, 0.05);
  });
  return <group ref={g}>{children}</group>;
}

export function HeroScene() {
  return (
    <>
      <Lights />
      <Pointer>
        <Float speed={1.4} rotationIntensity={0.25} floatIntensity={0.6}>
          <group position={[2.2, 0.1, 0]} scale={1.05}><Heart /><Rings /></group>
        </Float>
        <group position={[2.2, 0.1, 0]}><Network /></group>
      </Pointer>
      <Sparkles count={90} scale={[14, 8, 6]} size={2.4} speed={0.35} color="#7dd3fc" opacity={0.7} />
    </>
  );
}

export function AuthScene() {
  return (
    <>
      <Lights />
      <Pointer strength={0.2}>
        <Network count={64} radius={3.6} seed={21} spin={0.07} />
        <Float speed={1.2} floatIntensity={0.8}><group scale={0.7}><Heart /></group></Float>
      </Pointer>
      <Sparkles count={70} scale={[10, 8, 6]} size={2.2} speed={0.3} color="#a5b4fc" opacity={0.7} />
    </>
  );
}

const orbColor = { low: "#34d399", moderate: "#fbbf24", high: "#fb7185" } as const;
export function RiskOrb({ score, level }: { score: number; level: keyof typeof orbColor }) {
  const mesh = useRef<THREE.Mesh>(null!);
  useFrame((_, d) => { mesh.current.rotation.y += d * (0.25 + score * 0.6); mesh.current.rotation.x += d * 0.1; });
  const c = orbColor[level];
  return (
    <>
      <ambientLight intensity={0.7} />
      <pointLight position={[3, 3, 4]} intensity={40} color="#ffffff" />
      <pointLight position={[-4, -2, 3]} intensity={26} color={c} />
      <Float speed={1.6} floatIntensity={0.5}>
        <mesh ref={mesh}>
          <icosahedronGeometry args={[1.25, 24]} />
          <MeshDistortMaterial color={c} emissive={c} emissiveIntensity={0.35} roughness={0.2} metalness={0.5} distort={0.18 + score * 0.5} speed={1.2 + score * 3} />
        </mesh>
        <mesh scale={1.45}><icosahedronGeometry args={[1.25, 1]} /><meshBasicMaterial color={c} wireframe transparent opacity={0.16} /></mesh>
      </Float>
      <Sparkles count={40} scale={[5, 4, 4]} size={2} speed={0.4} color={c} opacity={0.8} />
    </>
  );
}
