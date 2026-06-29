import '@testing-library/jest-dom/vitest'

// Recharts' ResponsiveContainer measures its parent with ResizeObserver, which
// jsdom does not implement. Provide a no-op so charts render in tests, and give
// the container non-zero dimensions so child SVG elements actually mount.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver ?? (ResizeObserverStub as never)

// ResponsiveContainer measures its parent via offset dimensions AND
// getBoundingClientRect; jsdom reports zero for both. Force non-zero sizes so
// the SVG geometry (line paths, bar rectangles) actually renders.
Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
  configurable: true,
  value: 800,
})
Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
  configurable: true,
  value: 256,
})

const rect: DOMRect = {
  x: 0,
  y: 0,
  top: 0,
  left: 0,
  bottom: 256,
  right: 800,
  width: 800,
  height: 256,
  toJSON: () => ({}),
}
Object.defineProperty(HTMLElement.prototype, 'getBoundingClientRect', {
  configurable: true,
  value: () => rect,
})
Object.defineProperty(SVGElement.prototype, 'getBoundingClientRect', {
  configurable: true,
  value: () => rect,
})
