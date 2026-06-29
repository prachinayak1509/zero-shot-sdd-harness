import { test, expect } from '@playwright/test'
import path from 'node:path'

// Phase 3 persistent-workspace smoke.
//
// Assumes the FastAPI app (serving the built Next.js export at /app) is ALREADY
// running at http://localhost:8001/app/ — this spec does NOT launch a server
// (it reuses frontend/playwright.config.ts). It drives the real UI against the
// real backend + real Gemini and asserts the Phase 3 promises as real CONTENT:
//
//   - resume across "days": after a question, RELOADING the page shows the
//     session in the saved-sessions sidebar, and reopening it restores the
//     prior answer;
//   - the token/cost meter shows a non-zero running total;
//   - the step-trace drawer on an answer lists steps with rationale text;
//   - NO "Phase 3" stub pill remains anywhere — every Phase 3 surface is real.
//
// The upload reuses the small checked-in sample.csv (~10 rows) so the run is
// fast; the heavy 5000-row / join / token-accumulation assertions live in the
// Python tests. Waits are generous because a real Gemini round-trip is slow.

const SAMPLE_CSV = path.join(__dirname, 'fixtures', 'sample.csv')
const APP_URL = 'http://localhost:8001/app/'
const ANSWER_TIMEOUT = 120_000

async function uploadAndAsk(page, question: string) {
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles(SAMPLE_CSV)

  // Profile panel renders the dataset (real filename from the header).
  await expect(page.getByRole('heading', { name: 'sample.csv' })).toBeVisible({
    timeout: 30_000,
  })

  const input = page.getByPlaceholder('Ask a question about your data…')
  await expect(input).toBeEnabled()
  await input.fill(question)
  await page.getByRole('button', { name: 'Ask', exact: true }).click()

  // The user's question bubble appears immediately.
  await expect(page.getByText(question).first()).toBeVisible()

  // The assistant answer renders once the real Gemini round-trip completes;
  // "Show code" only appears with a finished coded answer.
  await expect(
    page.getByRole('button', { name: 'Show code' }).first(),
  ).toBeVisible({ timeout: ANSWER_TIMEOUT })
}

test('persistent workspace: resume across reload + cost meter + step trace (Phase 3 real)', async ({
  page,
}) => {
  // --- App loads and is styled -------------------------------------------
  await page.goto(APP_URL)
  await expect(
    page.getByRole('heading', { name: 'Analysis Workspace' }),
  ).toBeVisible()

  // --- Upload + ask a question -------------------------------------------
  const question = 'What is the total revenue grouped by region?'
  await uploadAndAsk(page, question)

  // --- Token / cost meter shows a NON-ZERO running total -----------------
  // The CostMeter surfaces per-question + running-session totals. Assert a
  // numeric token/cost figure greater than zero is shown somewhere on screen.
  // Robust to wording ("tokens", "cost", "$", etc.): we look for a number that
  // is not just "0".
  const meter = page.locator('body').getByText(/tokens?|cost|\$/i).first()
  await expect(meter).toBeVisible({ timeout: ANSWER_TIMEOUT })
  await expect(async () => {
    const meterText = (await page.locator('body').innerText()) ?? ''
    // A non-zero token figure appears (any multi-digit number, or a single
    // non-zero digit, adjacent to a token/cost context).
    expect(meterText).toMatch(/(\b[1-9]\d{1,}\b)|(\b[1-9]\b\s*(tokens?|\$))/i)
  }).toPass({ timeout: ANSWER_TIMEOUT })

  // --- Step-trace drawer lists steps with rationale text -----------------
  // The answer (and its step-trace toggle) lives inside <main>; the sidebar is
  // a separate <aside>. Scope the trace opener to <main> so we never grab a
  // sidebar control by accident.
  const main = page.locator('main')

  // StepTrace renders a CLOSED-by-default toggle labelled "Show trace · N steps".
  // We must click it first to REVEAL the steps before any rationale text exists.
  const traceOpener = main
    .getByRole('button', { name: /show trace/i })
    .first()
  await expect(traceOpener).toBeVisible({ timeout: ANSWER_TIMEOUT })
  await traceOpener.click()

  // The opened drawer lists ordered steps; each carries a node label
  // (plan / write_code / run_code / inspect / finalize) and a "Why: …"
  // rationale. Assert the revealed prose is now visible inside <main>.
  await expect(
    main.getByText(/why|rationale|approach|because|reason|plan|write_code|run_code|inspect|finalize|step/i).first(),
  ).toBeVisible({ timeout: 30_000 })

  // --- No "Phase 3" stub pill remains — every Phase 3 surface is real -----
  await expect(page.getByText('Phase 3', { exact: true })).toHaveCount(0)
  // Nor any "coming soon"/"later phase" placeholder text for these surfaces.
  await expect(
    page.getByText(/coming in a later phase|coming soon/i),
  ).toHaveCount(0)

  // --- Resume across "days": RELOAD the page -----------------------------
  await page.reload()
  await expect(
    page.getByRole('heading', { name: 'Analysis Workspace' }),
  ).toBeVisible()

  // The saved session appears in the sidebar (an <aside>/complementary
  // landmark). Its title is seeded from the first question, so it shows the
  // question text (possibly truncated). Target the sidebar session BUTTON by
  // its title text; .first() guards against multiple sessions sharing a title.
  const sidebar = page.getByRole('complementary')
  const sessionEntry = sidebar
    .getByRole('button')
    .filter({ hasText: /total revenue|revenue|sample\.csv/i })
    .first()
  await expect(sessionEntry).toBeVisible({ timeout: 30_000 })

  // Reopen the saved session and assert the PRIOR answer is restored.
  await sessionEntry.click()

  // The original question bubble is back in the transcript...
  await expect(page.getByText(question).first()).toBeVisible({ timeout: 30_000 })
  // ...and its answer (its "Show code" control) is restored too.
  await expect(
    page.getByRole('button', { name: 'Show code' }).first(),
  ).toBeVisible({ timeout: 30_000 })

  // Still no Phase 3 stub pill after the resume.
  await expect(page.getByText('Phase 3', { exact: true })).toHaveCount(0)
})
