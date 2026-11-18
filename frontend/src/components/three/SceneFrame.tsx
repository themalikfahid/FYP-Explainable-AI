import { Component, Suspense, type ReactNode } from "react";
import { Canvas } from "@react-three/fiber";

export function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch { return false; }
}
export const prefersReducedMotion = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

class Boundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { /* 3D is decorative: fall back silently */ }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

/** Decorative WebGL canvas. Falls back to a static gradient if WebGL is missing or the scene throws. */
export default function SceneFrame({ children, camera = [0, 0, 6.5], fov = 45, className = "", fallback }: {
  children: ReactNode; camera?: [number, number, number]; fov?: number; className?: string; fallback?: ReactNode;
}) {
  const fb = fallback ?? <div className={className} style={{ background: "radial-gradient(circle at 60% 40%, rgba(99,102,241,.35), transparent 60%)" }} aria-hidden />;
  if (typeof document === "undefined" || !webglAvailable()) return <>{fb}</>;
  return (
    <Boundary fallback={fb}>
      <Canvas className={className} dpr={[1, 1.75]} camera={{ position: camera, fov }} gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        frameloop={prefersReducedMotion() ? "demand" : "always"} aria-hidden="true">
        <Suspense fallback={null}>{children}</Suspense>
      </Canvas>
    </Boundary>
  );
}
