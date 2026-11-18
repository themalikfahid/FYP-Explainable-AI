import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom has no WebGL / ResizeObserver / matchMedia: stub what the UI touches.
class RO { observe() {} unobserve() {} disconnect() {} }
(globalThis as any).ResizeObserver = (globalThis as any).ResizeObserver ?? RO;
if (!window.matchMedia) {
  window.matchMedia = ((q: string) => ({ matches: false, media: q, onchange: null, addListener() {}, removeListener() {},
    addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false })) as any;
}
window.scrollTo = vi.fn() as any;
(globalThis as any).IntersectionObserver = (globalThis as any).IntersectionObserver ?? class {
  observe() {} unobserve() {} disconnect() {} takeRecords() { return []; }
};
