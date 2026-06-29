'use client'

import { useState } from 'react'
import { ApiError, saveDerived } from '@/lib/api'
import type { DerivedDataset } from '@/lib/types'

// "Save as dataset" control on an answer (Phase 3). Opens a small form
// pre-filled with the answer's code, POSTs to /api/datasets/{id}/derived, and
// on success shows the returned file path + recipe and hands the new derived
// dataset back to the workspace.

export function DerivedSave({
  datasetId,
  initialCode,
  defaultName,
  onSaved,
}: {
  datasetId: number | null
  initialCode: string
  defaultName?: string
  onSaved?: (ds: DerivedDataset) => void
}) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(defaultName ?? '')
  const [code, setCode] = useState(initialCode)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<DerivedDataset | null>(null)

  if (datasetId == null || !initialCode) return null

  async function handleSave() {
    if (datasetId == null) return
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Please give the dataset a name.')
      return
    }
    if (!code.trim()) {
      setError('There is no code to save.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const result = await saveDerived(datasetId, trimmed, code)
      setSaved(result)
      onSaved?.(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  if (saved) {
    return (
      <div className="mt-3 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">
        <p className="font-medium">Saved “{saved.name}” as a derived dataset.</p>
        <p className="mt-1 break-all font-mono text-xs text-green-700">{saved.file_path}</p>
        {saved.recipe && (
          <details className="mt-2">
            <summary className="cursor-pointer text-xs font-medium text-green-700">
              View recipe
            </summary>
            <pre className="mt-1.5 overflow-x-auto rounded-md bg-gray-900 p-2.5 text-[11px] leading-relaxed text-gray-100">
              <code className="font-mono">{saved.recipe}</code>
            </pre>
          </details>
        )}
        <p className="mt-2 text-xs text-green-700">Added to your workspace.</p>
      </div>
    )
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-3 flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:border-blue-300 hover:text-blue-700"
      >
        <svg
          className="h-3.5 w-3.5"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.8}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
          />
        </svg>
        Save as dataset
      </button>
    )
  }

  return (
    <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
      <p className="text-xs font-semibold text-gray-700">Save this result as a derived dataset</p>
      <p className="mt-0.5 text-[11px] text-gray-500">
        Stored as both a reusable file and a reproducible recipe.
      </p>

      <label className="mt-2 block text-[11px] font-medium uppercase tracking-wide text-gray-500">
        Name
      </label>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g. monthly_summary"
        className="mt-1 w-full rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-900 outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-300"
      />

      <label className="mt-2.5 block text-[11px] font-medium uppercase tracking-wide text-gray-500">
        Recipe (code)
      </label>
      <textarea
        value={code}
        onChange={(e) => setCode(e.target.value)}
        rows={4}
        spellCheck={false}
        className="mt-1 w-full rounded-md border border-gray-300 bg-gray-900 px-2.5 py-2 font-mono text-[11px] leading-relaxed text-gray-100 outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-300"
      />

      {error && (
        <p className="mt-2 rounded-md border border-red-200 bg-red-50 px-2.5 py-1.5 text-xs text-red-700">
          {error}
        </p>
      )}

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-60"
        >
          {saving ? 'Saving…' : 'Save dataset'}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          disabled={saving}
          className="rounded-md px-3 py-1.5 text-xs font-medium text-gray-500 hover:text-gray-700"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
