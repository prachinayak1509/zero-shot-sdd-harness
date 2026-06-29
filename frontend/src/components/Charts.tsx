'use client'

// Renders the agent's chosen chart_spec over the answer's `table` data using
// Recharts. chart_spec.type maps to a Recharts chart; x / y / series provide the
// encodings. When chart_spec is null we show a small inline note (NOT a stub).

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import type { ChartSpec, ResultTable } from '@/lib/types'

const PALETTE = [
  '#2563eb',
  '#16a34a',
  '#f59e0b',
  '#dc2626',
  '#7c3aed',
  '#0891b2',
  '#db2777',
  '#65a30d',
]

/** Turn the answer's columnar table into row objects keyed by column name. */
function toRecords(table: ResultTable): Record<string, unknown>[] {
  return table.rows.map((row) => {
    const rec: Record<string, unknown> = {}
    table.columns.forEach((col, i) => {
      rec[col] = row[i]
    })
    return rec
  })
}

/** Coerce a cell to a finite number where possible (Recharts needs numbers). */
function num(v: unknown): number | null {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v)
    return Number.isFinite(n) ? n : null
  }
  return null
}

export function Charts({
  chartSpec,
  table,
}: {
  chartSpec: ChartSpec | null | undefined
  table: ResultTable | null | undefined
}) {
  if (!chartSpec) {
    return (
      <div className="rounded-lg border border-gray-100 bg-gray-50/60 px-3 py-2 text-xs text-gray-500">
        No chart suited this result.
      </div>
    )
  }

  if (!table || table.columns.length === 0 || table.rows.length === 0) {
    return (
      <div className="rounded-lg border border-gray-100 bg-gray-50/60 px-3 py-2 text-xs text-gray-500">
        No data available to chart.
      </div>
    )
  }

  const data = toRecords(table)
  const { type, x, y, series, title } = chartSpec

  // Line charts silently render a blank SVG when the encodings don't resolve to
  // real columns or coerce to zero plottable points. Validate up front and fall
  // back to the same inline note used for a missing chart_spec.
  if (type === 'line' && !canPlotLine(table, x, y, series ?? null)) {
    return (
      <div className="rounded-lg border border-gray-100 bg-gray-50/60 px-3 py-2 text-xs text-gray-500">
        No chart suited this result.
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-gray-100 bg-white p-3">
      {title && <p className="mb-2 text-xs font-medium text-gray-600">{title}</p>}
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {renderChart(type, data, x, y, series ?? null)}
        </ResponsiveContainer>
      </div>
    </div>
  )
}

/**
 * Pivot long-format records into wide rows keyed by x, with one numeric column
 * per distinct series value. Returns the rows plus the ordered series keys so
 * the line renderer can emit one <Line> per series.
 */
function pivotBySeries(
  data: Record<string, unknown>[],
  x: string,
  y: string,
  series: string,
): { rows: Record<string, unknown>[]; keys: string[] } {
  const keys: string[] = []
  const byX = new Map<string, Record<string, unknown>>()
  for (const d of data) {
    const xKey = String(d[x] ?? '')
    const sKey = String(d[series] ?? '')
    if (!keys.includes(sKey)) keys.push(sKey)
    let row = byX.get(xKey)
    if (!row) {
      row = { [x]: d[x] }
      byX.set(xKey, row)
    }
    row[sKey] = num(d[y])
  }
  return { rows: Array.from(byX.values()), keys }
}

/**
 * Whether a line spec has any chance of plotting: x and y must resolve to real
 * columns, and after numeric coercion at least one point must exist.
 */
function canPlotLine(
  table: ResultTable,
  x: string,
  y: string,
  series: string | null,
): boolean {
  const cols = table.columns
  if (!cols.includes(x) || !cols.includes(y)) return false
  if (series && !cols.includes(series)) return false
  const data = toRecords(table)
  if (series) {
    const { rows, keys } = pivotBySeries(data, x, y, series)
    return rows.some((r) => keys.some((k) => num(r[k]) !== null))
  }
  return data.some((d) => num(d[y]) !== null)
}

function renderChart(
  type: string,
  data: Record<string, unknown>[],
  x: string,
  y: string,
  series: string | null,
): React.ReactElement {
  const axisProps = {
    tick: { fontSize: 11 },
    stroke: '#9ca3af',
  }

  switch (type) {
    case 'line': {
      // When series is set we pivot the long-format records into one numeric
      // column per series value and emit one <Line> each; otherwise we coerce y
      // to numbers in place and render a single line.
      if (series) {
        const { rows, keys } = pivotBySeries(data, x, y, series)
        return (
          <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey={x} {...axisProps} />
            <YAxis {...axisProps} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {keys.map((key, i) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={2}
                // A series with a single point would vanish without a dot.
                dot={rows.length <= 1}
                name={key}
                connectNulls
              />
            ))}
          </LineChart>
        )
      }
      const lineData = data.map((d) => ({ ...d, [y]: num(d[y]) }))
      return (
        <LineChart data={lineData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey={x} {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey={y}
            stroke={PALETTE[0]}
            strokeWidth={2}
            // Keep dots off for normal trends, but show them when the trend
            // collapses to a single row so it stays visible.
            dot={lineData.length <= 1}
            name={y}
          />
        </LineChart>
      )
    }

    case 'scatter':
      return (
        <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey={x} type="number" name={x} {...axisProps} />
          <YAxis dataKey={y} type="number" name={y} {...axisProps} />
          <ZAxis range={[40, 40]} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} />
          <Scatter
            data={data.map((d) => ({ ...d, [x]: num(d[x]), [y]: num(d[y]) }))}
            fill={PALETTE[0]}
            name={series ?? `${y} vs ${x}`}
          />
        </ScatterChart>
      )

    case 'pie':
      return (
        <PieChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Pie
            data={data.map((d) => ({ name: String(d[x] ?? ''), value: num(d[y]) ?? 0 }))}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius="80%"
            label={{ fontSize: 11 }}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
        </PieChart>
      )

    case 'bar':
    default:
      return (
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey={x} {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip />
          {series && <Legend wrapperStyle={{ fontSize: 12 }} />}
          <Bar dataKey={y} fill={PALETTE[0]} radius={[3, 3, 0, 0]} name={series ?? y}>
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Bar>
        </BarChart>
      )
  }
}
