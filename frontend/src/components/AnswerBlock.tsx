// Renders one assistant answer: prose answer, a step counter, the collapsible
// code panel, and the Phase-2 stubs (charts / table / follow-ups). When the
// run failed it renders a best-effort error card that STILL shows code/result.

import type { AskResult } from '@/lib/types'
import { CodePanel } from './CodePanel'
import { StubPanel } from './StubPanel'

export function AnswerBlock({ result }: { result: AskResult }) {
  const failed = result.status === 'failed'

  return (
    <div className="space-y-2">
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

      {/* Phase 2 stubs */}
      <div className="grid gap-2 pt-1 sm:grid-cols-2">
        <StubPanel title="Chart" phase="Phase 2" description="Agent-chosen interactive chart." />
        <StubPanel title="Result table" phase="Phase 2" description="Aggregated result rows." />
      </div>
      <StubPanel
        title="Suggested follow-ups"
        phase="Phase 2"
        description="Smart next-question chips."
      />
    </div>
  )
}
