import { defineConfig, devices } from '@playwright/test'

// Phase 1 Playwright config.
//
// The orchestrator / test skill starts the FastAPI app (which serves the
// built Next.js export at /app) BEFORE running these tests, so there is no
// `webServer` block here — the spec assumes the app is already up at
// http://localhost:8001/app/.
//
// testDir points at the repo-level tests/e2e (one level up from frontend/),
// so the suite lives alongside the Python end-to-end tests.
export default defineConfig({
  testDir: '../tests/e2e',
  testMatch: '**/*.spec.ts',
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  retries: 0,
  reporter: 'line',
  use: {
    baseURL: 'http://localhost:8001/app/',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
