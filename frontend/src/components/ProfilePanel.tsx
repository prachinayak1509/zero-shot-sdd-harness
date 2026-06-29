// Renders the real computed profile from the upload/get-dataset response:
// row count, per-column dtype/min/max/null_count, plus an optional sample table.

import type { Dataset } from '@/lib/types'
import { ColumnQualityBadges, QualityNotes } from './QualityBadges'

function fmt(v: string | number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return String(v)
  return String(v)
}

export function ProfilePanel({ dataset }: { dataset: Dataset }) {
  const { profile } = dataset
  const sample = profile.sample ?? []
  const sampleCols = sample.length > 0 ? Object.keys(sample[0]) : []

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-gray-900">{dataset.name}</h2>
          <p className="text-sm text-gray-500">
            {profile.columns.length} column{profile.columns.length === 1 ? '' : 's'} ·{' '}
            {dataset.row_count.toLocaleString()} row{dataset.row_count === 1 ? '' : 's'}
          </p>
        </div>
      </div>

      {/* Column profile table — REAL data */}
      <div className="mt-4 overflow-x-auto rounded-lg border border-gray-100">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-3 py-2 font-medium">Column</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Min</th>
              <th className="px-3 py-2 font-medium">Max</th>
              <th className="px-3 py-2 font-medium">Nulls</th>
              <th className="px-3 py-2 font-medium">Quality</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {profile.columns.map((col) => (
              <tr key={col.name} className="hover:bg-gray-50/60">
                <td className="px-3 py-2 font-medium text-gray-900">{col.name}</td>
                <td className="px-3 py-2">
                  <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-600">
                    {col.dtype}
                  </span>
                </td>
                <td className="px-3 py-2 text-gray-600">{fmt(col.min)}</td>
                <td className="px-3 py-2 text-gray-600">{fmt(col.max)}</td>
                <td className="px-3 py-2 text-gray-600">{col.null_count.toLocaleString()}</td>
                <td className="px-3 py-2">
                  <ColumnQualityBadges col={col} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Root data-quality summary — real values from the profile */}
      {profile.quality && (
        <QualityNotes
          notes={profile.quality.notes ?? []}
          totalFlags={profile.quality.total_flags ?? 0}
        />
      )}

      {/* Sample rows — REAL data when present */}
      {sample.length > 0 && (
        <div className="mt-4">
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-gray-500">
            Sample rows
          </p>
          <div className="overflow-x-auto rounded-lg border border-gray-100">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  {sampleCols.map((c) => (
                    <th key={c} className="px-3 py-2 font-medium">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sample.map((row, i) => (
                  <tr key={i} className="hover:bg-gray-50/60">
                    {sampleCols.map((c) => (
                      <td key={c} className="whitespace-nowrap px-3 py-2 text-gray-600">
                        {fmt(row[c] as string | number | null)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
