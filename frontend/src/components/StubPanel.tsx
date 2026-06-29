// A clearly-labelled, visibly-inert placeholder for a later-phase surface.
// Muted styling + a "Coming soon" pill so it's never mistaken for a bug.

interface StubPanelProps {
  title: string
  phase: string
  description?: string
  className?: string
}

export function StubPanel({ title, phase, description, className = '' }: StubPanelProps) {
  return (
    <div
      aria-disabled="true"
      className={`select-none rounded-lg border border-dashed border-gray-300 bg-gray-50/70 p-4 text-gray-400 ${className}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-gray-500">{title}</span>
        <span className="whitespace-nowrap rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
          {phase}
        </span>
      </div>
      {description && <p className="mt-1.5 text-xs text-gray-400">{description}</p>}
    </div>
  )
}

/** A small inline "Coming soon" chip for tab-like stubs. */
export function StubPill({ label }: { label: string }) {
  return (
    <span className="whitespace-nowrap rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
      {label}
    </span>
  )
}
