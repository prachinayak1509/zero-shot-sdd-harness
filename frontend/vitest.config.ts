import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

// Component-level unit tests run under jsdom with Vitest. These are distinct
// from the Playwright E2E suite (../tests/e2e/**/*.spec.ts), which needs a
// running server. We match *.test.ts(x) only so the two never collide.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['./vitest.setup.ts'],
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
