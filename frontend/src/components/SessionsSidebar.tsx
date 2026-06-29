'use client'

import type { SessionSummary } from '@/lib/types'
import { CostMeter } from './CostMeter'

// Left sidebar (Phase 3, real). Lists saved sessions (resume across days),
// offers a "New session" action, and shows the live token / cost meter.

function fmtWhen(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function SessionsSidebar({
  sessions,
  loading,
  error,
  activeConversationId,
  onResume,
  onNewSession,
  lastQuestionTokens,
  sessionTokens,
}: {
  sessions: SessionSummary[]
  loading: boolean
  error: string | null
  activeConversationId: number | null
  onResume: (id: number) => void
  onNewSession: () => void
  lastQuestionTokens: number | null
  sessionTokens: number
}) {
  return (
    <aside className="hidden w-64 shrink-0 flex-col gap-3 border-r border-gray-200 bg-white/60 p-4 lg:flex">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
          D
        </div>
        <span className="text-sm font-semibold text-gray-900">Data Analyst</span>
      </div>

      <button
        type="button"
        onClick={onNewSession}
        className="mt-2 flex items-center justify-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:border-blue-300 hover:text-blue-700"
      >
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.8}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
        </svg>
        New session
      </button>

      <div className="mt-1 min-h-0 flex-1 overflow-y-auto">
        <p className="mb-1.5 px-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
          Saved sessions
        </p>

        {loading ? (
          <p className="px-1 py-2 text-xs text-gray-400">Loading sessions…</p>
        ) : error ? (
          <p className="rounded-md border border-red-200 bg-red-50 px-2 py-1.5 text-xs text-red-600">
            {error}
          </p>
        ) : sessions.length === 0 ? (
          <p className="px-1 py-2 text-xs text-gray-400">
            No saved sessions yet. Upload a file and ask a question to start one.
          </p>
        ) : (
          <ul className="space-y-1">
            {sessions.map((s) => {
              const active = s.id === activeConversationId
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => onResume(s.id)}
                    aria-current={active ? 'true' : undefined}
                    className={`w-full rounded-lg px-2.5 py-2 text-left transition-colors ${
                      active
                        ? 'bg-blue-50 ring-1 ring-blue-200'
                        : 'hover:bg-gray-100'
                    }`}
                  >
                    <p className="truncate text-sm font-medium text-gray-800">
                      {s.title?.trim() || `Session ${s.id}`}
                    </p>
                    <p className="text-[11px] text-gray-400">{fmtWhen(s.updated_at)}</p>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div className="mt-auto">
        <CostMeter lastQuestionTokens={lastQuestionTokens} sessionTokens={sessionTokens} />
      </div>
    </aside>
  )
}
