// Token / cost meter (Phase 3). Shows the most-recent answer's per-question
// token usage and a running session total. The session total is kept in
// page state (accumulated from each ask response and reconciled with the
// backend's session_tokens on reload).

function fmtTokens(n: number): string {
  return n.toLocaleString()
}

export function CostMeter({
  lastQuestionTokens,
  sessionTokens,
}: {
  lastQuestionTokens: number | null
  sessionTokens: number
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-900">Tokens</span>
        <svg
          className="h-4 w-4 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Z"
          />
        </svg>
      </div>

      <dl className="mt-3 space-y-2">
        <div className="flex items-baseline justify-between">
          <dt className="text-xs text-gray-500">This question</dt>
          <dd className="font-mono text-sm font-semibold text-gray-900">
            {lastQuestionTokens == null ? '—' : fmtTokens(lastQuestionTokens)}
          </dd>
        </div>
        <div className="flex items-baseline justify-between border-t border-gray-100 pt-2">
          <dt className="text-xs text-gray-500">Session total</dt>
          <dd className="font-mono text-sm font-semibold text-blue-700">
            {fmtTokens(sessionTokens)}
          </dd>
        </div>
      </dl>
    </div>
  )
}
