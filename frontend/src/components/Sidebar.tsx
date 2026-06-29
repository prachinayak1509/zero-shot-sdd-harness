// Left sidebar. In Phase 1 the saved-sessions list and the cost meter are
// labelled, inert Phase-3 stubs.

import { StubPanel } from './StubPanel'

export function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 flex-col gap-3 border-r border-gray-200 bg-white/60 p-4 lg:flex">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
          D
        </div>
        <span className="text-sm font-semibold text-gray-900">Data Analyst</span>
      </div>

      <StubPanel
        title="Saved sessions"
        phase="Phase 3"
        description="Resume conversations across days."
        className="mt-2"
      />

      <StubPanel
        title="Token / cost meter"
        phase="Phase 3"
        description="Per-question and running totals."
      />

      <div className="mt-auto">
        <StubPanel
          title="Full step-trace"
          phase="Phase 3"
          description="Step-by-step “why this approach”."
        />
      </div>
    </aside>
  )
}
