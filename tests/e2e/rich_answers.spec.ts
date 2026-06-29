import { test, expect } from '@playwright/test'
import path from 'node:path'

// Phase 2 rich-answers smoke.
//
// Assumes the FastAPI app (serving the built Next.js export at /app) is ALREADY
// running at http://localhost:8001/app/ — this spec does NOT launch a server.
// It drives the real UI against the real backend + real Gemini and asserts real
// CONTENT (a rendered chart, an aggregated result table, clickable follow-ups,
// and data-quality badges), not just HTTP 200s.
//
// The upload uses a small checked-in CSV (~30 rows) with a clear categorical
// column (region), a numeric column (revenue), and a couple of blank revenue
// cells + one obvious outlier so the data-quality badges have something to
// surface; the heavy 5000-row assertions live in the Python tests.

const RICH_CSV = path.join(__dirname, 'fixtures', 'rich.csv')

test('rich answers: chart + table + follow-ups + quality badges (Phase 2 real)', async ({
  page,
}) => {
  // --- App loads and is styled -------------------------------------------
  await page.goto('http://localhost:8001/app/')
  await expect(page.getByRole('heading', { name: 'Analysis Workspace' })).toBeVisible()

  // --- Upload the rich fixture -------------------------------------------
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles(RICH_CSV)

  // Profile panel renders the dataset (real column names from the header).
  await expect(page.getByRole('heading', { name: 'rich.csv' })).toBeVisible({
    timeout: 30_000,
  })

  // --- Data-quality badge is visible on the profile ----------------------
  // The QualityBadges component surfaces null %/outlier flags computed from the
  // file. Assert at least one quality badge appears (text mentions null,
  // outlier, or a percentage) — robust to exact wording.
  await expect(
    page.locator('body').getByText(/null|outlier|%|missing/i).first(),
  ).toBeVisible({ timeout: 30_000 })

  // --- Phase 2 surfaces are now REAL — no "Phase 2" stub pill remains -----
  // (Phase 3 stubs may still be present; we only forbid the Phase 2 label.)
  await expect(page.getByText('Phase 2', { exact: true })).toHaveCount(0)

  // --- Ask a grouping question -------------------------------------------
  const question = 'What is the total revenue grouped by region?'
  const input = page.getByPlaceholder('Ask a question about your data…')
  await expect(input).toBeEnabled()
  await input.fill(question)
  await page.getByRole('button', { name: 'Ask', exact: true }).click()

  // The user's question bubble appears immediately.
  await expect(page.getByText(question).first()).toBeVisible()

  // The answers (chart / table / follow-ups / Show code) live inside <main>;
  // the saved-sessions sidebar is a separate <aside>. Scope every answer-area
  // locator to <main> so a sidebar session button (whose title contains "?")
  // can never satisfy or break a follow-up/answer assertion.
  const main = page.locator('main')

  // --- A real CHART renders (Recharts emits an <svg>/<canvas>) ------------
  // Recharts renders into a .recharts-wrapper containing an <svg class="recharts-surface">.
  const chart = main
    .locator('svg.recharts-surface, .recharts-wrapper svg, .recharts-responsive-container svg, canvas')
    .first()
  await expect(chart).toBeVisible({ timeout: 90_000 })

  // --- A real RESULT TABLE renders with >= 2 aggregated rows --------------
  // The Result Table renders the aggregated group-by rows (one per region).
  const tableRows = main.locator('table tbody tr')
  await expect(tableRows.first()).toBeVisible({ timeout: 90_000 })
  expect(await tableRows.count()).toBeGreaterThanOrEqual(2)

  // --- Suggested FOLLOW-UP chips render ----------------------------------
  // The FollowUps strip renders clickable suggestion buttons inside the answer
  // area. They are buttons distinct from the primary "Ask" button; assert at
  // least two are present. Scoped to <main> so sidebar session buttons (whose
  // titles also contain "?") are excluded.
  const followUps = main.getByRole('button').filter({ hasText: /\?/ })
  await expect(followUps.first()).toBeVisible({ timeout: 90_000 })
  const followUpCount = await followUps.count()
  expect(followUpCount).toBeGreaterThanOrEqual(2)

  // --- Count answer blocks before clicking a follow-up -------------------
  // Each assistant answer exposes a "Show code" control; count them as a proxy
  // for the number of rendered answers.
  const answerMarkers = main.getByRole('button', { name: 'Show code' })
  const beforeCount = await answerMarkers.count()
  expect(beforeCount).toBeGreaterThanOrEqual(1)

  // --- Clicking a follow-up triggers a NEW answer ------------------------
  await followUps.first().click()
  // A second answer block appears (one more "Show code" control than before).
  await expect(async () => {
    expect(await answerMarkers.count()).toBeGreaterThan(beforeCount)
  }).toPass({ timeout: 90_000 })
})
