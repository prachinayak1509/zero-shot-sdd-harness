// Small data-quality badges computed deterministically on the profile:
// per-column null % and outlier count, plus arbitrary string flags. Used inside
// ProfilePanel's column rows and for the root quality summary.

import type { ProfileColumn } from '@/lib/types'

function Badge({
  tone,
  children,
}: {
  tone: 'amber' | 'red' | 'gray'
  children: React.ReactNode
}) {
  const cls =
    tone === 'red'
      ? 'bg-red-100 text-red-700'
      : tone === 'amber'
        ? 'bg-amber-100 text-amber-700'
        : 'bg-gray-100 text-gray-600'
  return (
    <span
      className={`whitespace-nowrap rounded-full px-1.5 py-0.5 text-[10px] font-medium ${cls}`}
    >
      {children}
    </span>
  )
}

/** Inline quality badges for a single profile column. Renders nothing when clean. */
export function ColumnQualityBadges({ col }: { col: ProfileColumn }) {
  const badges: React.ReactNode[] = []

  if (typeof col.null_pct === 'number' && col.null_pct > 0) {
    const pct = Math.round(col.null_pct)
    badges.push(
      <Badge key="null" tone={col.null_pct >= 20 ? 'red' : 'amber'}>
        {pct}% null
      </Badge>,
    )
  }

  if (typeof col.outlier_count === 'number' && col.outlier_count > 0) {
    badges.push(
      <Badge key="out" tone="amber">
        {col.outlier_count.toLocaleString()} outlier{col.outlier_count === 1 ? '' : 's'}
      </Badge>,
    )
  }

  for (const flag of col.flags ?? []) {
    badges.push(
      <Badge key={`flag-${flag}`} tone="gray">
        {flag}
      </Badge>,
    )
  }

  if (badges.length === 0) return null
  return <div className="flex flex-wrap gap-1">{badges}</div>
}

/** Root data-quality summary: total flag count + short notes list. */
export function QualityNotes({ notes, totalFlags }: { notes: string[]; totalFlags: number }) {
  if (totalFlags === 0 && notes.length === 0) return null

  return (
    <div className="mt-4 rounded-lg border border-amber-100 bg-amber-50/60 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
        Data quality
        {totalFlags > 0 && (
          <span className="ml-1.5 rounded-full bg-amber-200 px-1.5 py-0.5 text-[10px] text-amber-800">
            {totalFlags} flag{totalFlags === 1 ? '' : 's'}
          </span>
        )}
      </p>
      {notes.length > 0 && (
        <ul className="mt-1.5 list-inside list-disc space-y-0.5 text-xs text-amber-800">
          {notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
