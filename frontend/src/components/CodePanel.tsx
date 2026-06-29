'use client'

import { useState } from 'react'

// Collapsible "Show code" panel — collapsed by default. Reveals the exact
// pandas code and the raw result_repr.

interface CodePanelProps {
  code: string
  resultRepr: string
}

export function CodePanel({ code, resultRepr }: CodePanelProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium text-gray-600 hover:text-gray-900"
      >
        <span>{open ? 'Hide code' : 'Show code'}</span>
        <svg
          className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {open && (
        <div className="space-y-3 border-t border-gray-200 p-3">
          {code && (
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-400">
                pandas
              </p>
              <pre className="overflow-x-auto rounded-md bg-gray-900 p-3 text-xs leading-relaxed text-gray-100">
                <code className="font-mono">{code}</code>
              </pre>
            </div>
          )}
          {resultRepr && (
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-400">
                result
              </p>
              <pre className="overflow-x-auto rounded-md border border-gray-200 bg-white p-3 text-xs leading-relaxed text-gray-700">
                <code className="font-mono">{resultRepr}</code>
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
