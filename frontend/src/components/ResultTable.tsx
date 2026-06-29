// Renders the answer's aggregated `table` ({columns, rows}) as a real scrollable
// HTML table. Visible rows are capped; the total count is shown. Hidden when null.

import type { ResultTable as ResultTableData } from '@/lib/types'

const MAX_VISIBLE_ROWS = 50

function fmtCell(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') {
    return Number.isInteger(v) ? String(v) : v.toFixed(4).replace(/\.?0+$/, '')
  }
  return String(v)
}

export function ResultTable({ table }: { table: ResultTableData | null | undefined }) {
  if (!table || table.columns.length === 0) return null

  const total = table.rows.length
  const visible = table.rows.slice(0, MAX_VISIBLE_ROWS)

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Result table</p>
        <p className="text-[11px] text-gray-400">
          {total.toLocaleString()} row{total === 1 ? '' : 's'}
          {total > MAX_VISIBLE_ROWS ? ` · showing first ${MAX_VISIBLE_ROWS}` : ''}
        </p>
      </div>
      <div className="max-h-72 overflow-auto rounded-lg border border-gray-100">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="sticky top-0 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              {table.columns.map((c) => (
                <th key={c} className="whitespace-nowrap px-3 py-2 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {visible.map((row, i) => (
              <tr key={i} className="hover:bg-gray-50/60">
                {table.columns.map((_, j) => (
                  <td key={j} className="whitespace-nowrap px-3 py-2 text-gray-700">
                    {fmtCell(row[j])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
