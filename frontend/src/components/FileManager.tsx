'use client'

import { useRef, useState } from 'react'
import type { Dataset } from '@/lib/types'

// "+ Add file / sheet" control (Phase 3). Adds MORE files (CSV or .xlsx) to the
// current workspace and lists every loaded table — one per file / per xlsx
// sheet — by its name, so the user can ask join/compare questions.

function isAccepted(file: File): boolean {
  const n = file.name.toLowerCase()
  return (
    n.endsWith('.csv') ||
    n.endsWith('.xlsx') ||
    file.type === 'text/csv' ||
    file.type === 'application/vnd.ms-excel' ||
    file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  )
}

export function FileManager({
  datasets,
  onAddFiles,
  adding,
  error,
}: {
  datasets: Dataset[]
  onAddFiles: (files: File[]) => void
  adding: boolean
  error: string | null
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  function handleFiles(fileList: FileList | null) {
    setLocalError(null)
    const files = fileList ? Array.from(fileList) : []
    if (files.length === 0) return
    const bad = files.filter((f) => !isAccepted(f))
    if (bad.length > 0) {
      setLocalError('Only .csv and .xlsx files are supported.')
      return
    }
    onAddFiles(files)
  }

  const shownError = localError ?? error

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Workspace tables</h3>
          <p className="text-xs text-gray-500">
            Add more files to join or compare across tables.
          </p>
        </div>
        <button
          type="button"
          onClick={() => !adding && inputRef.current?.click()}
          disabled={adding}
          className="flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 transition-colors hover:bg-blue-100 disabled:opacity-60"
        >
          {adding ? (
            <>
              <Spinner />
              Adding…
            </>
          ) : (
            <>
              <svg
                className="h-3.5 w-3.5"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              Add file / sheet
            </>
          )}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,text/csv"
          multiple
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {datasets.length > 0 ? (
        <ul className="mt-3 flex flex-wrap gap-2">
          {datasets.map((ds) => (
            <li
              key={ds.id}
              className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5"
            >
              <span className="flex h-5 w-5 items-center justify-center rounded bg-blue-100 text-[10px] font-bold text-blue-700">
                T
              </span>
              <span className="text-xs font-medium text-gray-800">{ds.name}</span>
              <span className="text-[10px] text-gray-400">
                {ds.row_count.toLocaleString()} rows
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-xs text-gray-400">No tables loaded yet.</p>
      )}

      {shownError && (
        <div className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {shownError}
        </div>
      )}
    </section>
  )
}

function Spinner() {
  return (
    <svg className="h-3.5 w-3.5 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}
