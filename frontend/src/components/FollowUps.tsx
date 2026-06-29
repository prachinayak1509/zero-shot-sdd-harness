// Renders the agent's `follow_ups` as clickable chips. Clicking a chip re-asks
// that question in the SAME conversation via the onAskFollowUp handler wired
// from page.tsx (which reuses handleAsk with the active conversation_id).

export function FollowUps({
  followUps,
  onAskFollowUp,
  disabled = false,
}: {
  followUps: string[] | null | undefined
  onAskFollowUp: (question: string) => void
  disabled?: boolean
}) {
  if (!followUps || followUps.length === 0) return null

  return (
    <div>
      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-gray-500">
        Suggested follow-ups
      </p>
      <div className="flex flex-wrap gap-2">
        {followUps.map((q, i) => (
          <button
            key={i}
            type="button"
            disabled={disabled}
            onClick={() => onAskFollowUp(q)}
            className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 transition hover:border-blue-300 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
