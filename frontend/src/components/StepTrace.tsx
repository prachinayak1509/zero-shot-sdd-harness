'use client'

import { useState } from 'react'
import type { Step } from '@/lib/types'

// Full step-trace drawer (Phase 3). Opened from an AnswerBlock, it reveals the
// ordered steps the agent took for that answer — each step's node, its
// "why this approach" rationale, the code it ran, and its token usage.

export function StepTrace({ steps }: { steps?: Step[] | null }) {
  const [open, setOpen] = useState(false)

  if (!steps || steps.length === 0) return null

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:border-gray-300 hover:text-gray-900"
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
            d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
          />
        </svg>
        <span>
          {open ? 'Hide trace' : 'Show trace'} · {steps.length} step
          {steps.length === 1 ? '' : 's'}
        </span>
      </button>

      {open && (
        <ol className="mt-2 space-y-2 border-l-2 border-gray-100 pl-4">
          {steps.map((step, i) => (
            <li key={i} className="relative">
              <span className="absolute -left-[1.4rem] top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-[10px] font-bold text-blue-700">
                {i + 1}
              </span>
              <div className="rounded-lg border border-gray-200 bg-gray-50/70 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-gray-200 px-1.5 py-0.5 font-mono text-[11px] text-gray-700">
                    {step.node || 'step'}
                  </span>
                  {step.tokens != null && (
                    <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-600">
                      {step.tokens.toLocaleString()} tok
                    </span>
                  )}
                  {step.error && (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                      error
                    </span>
                  )}
                </div>

                {step.rationale && (
                  <p className="mt-2 text-xs leading-relaxed text-gray-600">
                    <span className="font-semibold text-gray-700">Why: </span>
                    {step.rationale}
                  </p>
                )}

                {step.code && (
                  <pre className="mt-2 overflow-x-auto rounded-md bg-gray-900 p-2.5 text-[11px] leading-relaxed text-gray-100">
                    <code className="font-mono">{step.code}</code>
                  </pre>
                )}

                {step.result_repr && (
                  <pre className="mt-2 overflow-x-auto rounded-md border border-gray-200 bg-white p-2.5 text-[11px] leading-relaxed text-gray-700">
                    <code className="font-mono">{step.result_repr}</code>
                  </pre>
                )}

                {step.error && (
                  <pre className="mt-2 overflow-x-auto rounded-md border border-amber-200 bg-amber-50 p-2.5 text-[11px] leading-relaxed text-amber-800">
                    <code className="font-mono">{step.error}</code>
                  </pre>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
