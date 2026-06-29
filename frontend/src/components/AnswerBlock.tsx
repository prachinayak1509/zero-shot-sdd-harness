// Renders one assistant answer: prose answer, a step counter, the collapsible
// code panel, then the rich Phase-2 surfaces — the agent-chosen chart, the
// aggregated result table, and clickable follow-up chips. When the run failed it
// renders a best-effort error card that STILL shows code/result.

import type { AskResult } from '@/lib/types'
import { CodePanel } from './CodePanel'
import { Charts } from './Charts'
import { ResultTable } from './ResultTable'
import { FollowUps } from './FollowUps'

export function AnswerBlock({
  result,
  onAskFollowUp,
  followUpsDisabled = false,
}: {
  result: AskResult
  onAskFollowUp: (question: string) => void
  followUpsDisabled?: boolean
}) {
  const failed = result.status === 'failed'

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500">
          {result.step_count} step{result.step_count === 1 ? '' : 's'}
        </span>
        {result.effort && (
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium capitalize text-gray-500">
            {result.effort}
          </span>
        )}
        {failed && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700">
            Best effort
          </span>
        )}
      </div>

      {failed ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">This run didn&apos;t fully complete.</p>
          <p className="mt-1 whitespace-pre-wrap text-amber-800">
            {result.answer || 'The agent stopped before producing a final answer.'}
          </p>
          <p className="mt-1 text-xs text-amber-700">
            The code and result captured so far are shown below.
          </p>
        </div>
      ) : (
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-800">
          {result.answer}
        </p>
      )}

      {(result.code || result.result_repr) && (
        <CodePanel code={result.code} resultRepr={result.result_repr} />
      )}

      {/* Rich Phase-2 surfaces — chart, table, follow-ups. */}
      {!failed && (
        <>
          <Charts chartSpec={result.chart_spec} table={result.table} />
          <ResultTable table={result.table} />
          <FollowUps
            followUps={result.follow_ups}
            onAskFollowUp={onAskFollowUp}
            disabled={followUpsDisabled}
          />
        </>
      )}
    </div>
  )
}
