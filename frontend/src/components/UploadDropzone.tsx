'use client'

import { useRef, useState } from 'react'

interface UploadDropzoneProps {
  onFile: (file: File) => void
  uploading: boolean
  error: string | null
  /** Name of the currently-loaded dataset, if any. */
  loadedName?: string | null
}

function isCsv(file: File): boolean {
  return (
    file.name.toLowerCase().endsWith('.csv') ||
    file.type === 'text/csv' ||
    file.type === 'application/vnd.ms-excel'
  )
}

export function UploadDropzone({ onFile, uploading, error, loadedName }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  function handleFiles(files: FileList | null) {
    setLocalError(null)
    const file = files?.[0]
    if (!file) return
    if (!isCsv(file)) {
      setLocalError('Please choose a .csv file.')
      return
    }
    onFile(file)
  }

  const shownError = localError ?? error

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => !uploading && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !uploading) inputRef.current?.click()
        }}
        onDragOver={(e) => {
          e.preventDefault()
          if (!uploading) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (!uploading) handleFiles(e.dataTransfer.files)
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors ${
          dragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 bg-white hover:border-blue-400 hover:bg-blue-50/40'
        } ${uploading ? 'pointer-events-none opacity-70' : ''}`}
      >
        {uploading ? (
          <>
            <Spinner />
            <p className="text-sm font-medium text-gray-700">Profiling your CSV…</p>
            <p className="text-xs text-gray-400">Reading columns, types and ranges.</p>
          </>
        ) : (
          <>
            <svg
              className="h-8 w-8 text-blue-500"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
              />
            </svg>
            <p className="text-sm font-medium text-gray-700">
              {loadedName ? 'Replace dataset' : 'Drop a CSV here or click to choose'}
            </p>
            <p className="text-xs text-gray-400">One CSV file. We&apos;ll profile it instantly.</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {loadedName && !uploading && (
        <p className="mt-2 text-xs text-gray-500">
          Loaded: <span className="font-medium text-gray-700">{loadedName}</span>
        </p>
      )}

      {shownError && (
        <div className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {shownError}
        </div>
      )}
    </div>
  )
}

function Spinner() {
  return (
    <svg className="h-7 w-7 animate-spin text-blue-500" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}
