import { test, expect } from '@playwright/test'
import path from 'node:path'

// Phase 1 primary-journey smoke.
//
// Assumes the FastAPI app (serving the built Next.js export at /app) is ALREADY
// running at http://localhost:8001/app/ — this spec does NOT launch a server.
// It drives the real UI against the real backend + real Gemini, asserting real
// CONTENT (column names, an answer, the pandas code), not just HTTP 200s.
//
// The upload uses a small checked-in CSV (~10 rows) so the run is fast; the
// 5000-row reproducibility check lives in the Python end-to-end test.

const SAMPLE_CSV = path.join(__dirname, 'fixtures', 'sample.csv')

test('upload -> profile -> ask -> coded answer (with labelled stubs)', async ({ page }) => {
  // --- App loads and is styled -------------------------------------------
  await page.goto('http://localhost:8001/app/')
  await expect(page.getByRole('heading', { name: 'Analysis Workspace' })).toBeVisible()

  // --- Upload control renders --------------------------------------------
  const dropzone = page.getByText('Drop a CSV here or click to choose')
  await expect(dropzone).toBeVisible()

  // --- Set the (hidden) file input to the sample CSV ----------------------
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles(SAMPLE_CSV)

  // --- Profile panel shows REAL column names from the uploaded file -------
  // ProfilePanel renders the dataset name and a column table.
  await expect(page.getByRole('heading', { name: 'sample.csv' })).toBeVisible({ timeout: 30_000 })
  // Real column names from the CSV header appear in the profile table.
  for (const col of ['region', 'product', 'units', 'revenue']) {
    await expect(page.getByRole('cell', { name: col, exact: true }).first()).toBeVisible()
  }

  // --- Labelled, inert stubs are PRESENT (not bugs) -----------------------
  // The workspace renders "Coming in a later phase" style stubs tagged with a
  // phase pill (e.g. "Phase 2"). At least one must be visible.
  await expect(page.getByText('Phase 2', { exact: true }).first()).toBeVisible()

  // --- Ask a question -----------------------------------------------------
  const question = 'What is the total revenue grouped by region?'
  const input = page.getByPlaceholder('Ask a question about your data…')
  await expect(input).toBeEnabled()
  await input.fill(question)
  await page.getByRole('button', { name: 'Ask', exact: true }).click()

  // The user's question bubble appears immediately.
  await expect(page.getByText(question).first()).toBeVisible()

  // --- Assistant answer renders (real Gemini round-trip; allow time) ------
  // "Show code" only appears once the answer (with its code) has rendered.
  const showCode = page.getByRole('button', { name: 'Show code' })
  await expect(showCode.first()).toBeVisible({ timeout: 90_000 })

  // --- Reveal the code panel; it shows real pandas text -------------------
  await showCode.first().click()
  await expect(page.getByText('pandas', { exact: true }).first()).toBeVisible()
  // The revealed <pre><code> contains pandas referencing a real column.
  const codeBlock = page.locator('pre code').first()
  await expect(codeBlock).toBeVisible()
  await expect(codeBlock).toContainText(/region|revenue/)
})
