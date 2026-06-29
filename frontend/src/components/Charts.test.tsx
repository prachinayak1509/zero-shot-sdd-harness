import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Charts } from './Charts'
import type { ChartSpec, ResultTable } from '@/lib/types'

// Regression coverage for the Phase 2 bug where trend-over-time (line) charts
// rendered a silent blank SVG while bar/grouping charts worked. These tests
// drive a line chart_spec end-to-end through <Charts /> and assert real line
// paths render, that string-typed numerics still plot, that multi-series specs
// emit one line per series, and that unplottable specs fall back to the
// "No chart suited this result." note instead of an empty box.

function lineCount(container: HTMLElement): number {
  // Recharts renders each <Line> as a .recharts-line group containing a
  // .recharts-line-curve path.
  return container.querySelectorAll('.recharts-line-curve').length
}

const FALLBACK = 'No chart suited this result.'

describe('Charts — line (trend over time)', () => {
  it('renders a line path for a numeric time-trend spec', () => {
    const table: ResultTable = {
      columns: ['month', 'revenue'],
      rows: [
        ['2024-01', 1200],
        ['2024-02', 1500],
        ['2024-03', 1800],
      ],
    }
    const spec: ChartSpec = { type: 'line', x: 'month', y: 'revenue', title: 'Revenue by month' }

    const { container } = render(<Charts chartSpec={spec} table={table} />)

    expect(screen.queryByText(FALLBACK)).not.toBeInTheDocument()
    expect(lineCount(container)).toBe(1)
  })

  it('plots string-typed numeric y values via num() coercion', () => {
    const table: ResultTable = {
      columns: ['month', 'revenue'],
      rows: [
        ['2024-01', '1200'],
        ['2024-02', '1500'],
        ['2024-03', '1800'],
      ],
    }
    const spec: ChartSpec = { type: 'line', x: 'month', y: 'revenue' }

    const { container } = render(<Charts chartSpec={spec} table={table} />)

    expect(screen.queryByText(FALLBACK)).not.toBeInTheDocument()
    expect(lineCount(container)).toBe(1)
  })

  it('renders one line per series for a multi-series (long-format) spec', () => {
    const table: ResultTable = {
      columns: ['month', 'category', 'revenue'],
      rows: [
        ['2024-01', 'A', 100],
        ['2024-01', 'B', 200],
        ['2024-02', 'A', 150],
        ['2024-02', 'B', 250],
        ['2024-03', 'A', 175],
        ['2024-03', 'B', 275],
      ],
    }
    const spec: ChartSpec = {
      type: 'line',
      x: 'month',
      y: 'revenue',
      series: 'category',
      title: 'Revenue per month by category',
    }

    const { container } = render(<Charts chartSpec={spec} table={table} />)

    expect(screen.queryByText(FALLBACK)).not.toBeInTheDocument()
    // Two distinct categories => two lines, not one mismatched line.
    expect(lineCount(container)).toBe(2)
  })

  it('renders a visible single-point trend instead of a blank box', () => {
    const table: ResultTable = {
      columns: ['month', 'revenue'],
      rows: [['2024-01', 1200]],
    }
    const spec: ChartSpec = { type: 'line', x: 'month', y: 'revenue' }

    const { container } = render(<Charts chartSpec={spec} table={table} />)

    // A single point has no curve geometry, so it must stay visible via a dot.
    // The bug we guard against is a totally blank SVG: assert the line group
    // mounts AND a dot circle is drawn, and that it did not fall back.
    expect(screen.queryByText(FALLBACK)).not.toBeInTheDocument()
    expect(container.querySelectorAll('.recharts-line').length).toBe(1)
    expect(container.querySelectorAll('.recharts-line .recharts-dot').length).toBeGreaterThan(0)
  })

  it('falls back to the note when y does not resolve to a real column', () => {
    const table: ResultTable = {
      columns: ['month', 'revenue'],
      rows: [
        ['2024-01', 1200],
        ['2024-02', 1500],
      ],
    }
    // y references a column that is not in the table.
    const spec: ChartSpec = { type: 'line', x: 'month', y: 'profit' }

    const { container } = render(<Charts chartSpec={spec} table={table} />)

    expect(screen.getByText(FALLBACK)).toBeInTheDocument()
    expect(lineCount(container)).toBe(0)
  })

  it('falls back to the note when no y value coerces to a number', () => {
    const table: ResultTable = {
      columns: ['month', 'revenue'],
      rows: [
        ['2024-01', 'n/a'],
        ['2024-02', 'pending'],
      ],
    }
    const spec: ChartSpec = { type: 'line', x: 'month', y: 'revenue' }

    const { container } = render(<Charts chartSpec={spec} table={table} />)

    expect(screen.getByText(FALLBACK)).toBeInTheDocument()
    expect(lineCount(container)).toBe(0)
  })
})

describe('Charts — bar (no regression)', () => {
  it('still renders a bar chart for a grouping spec', () => {
    const table: ResultTable = {
      columns: ['category', 'count'],
      rows: [
        ['A', 10],
        ['B', 20],
        ['C', 30],
      ],
    }
    const spec: ChartSpec = { type: 'bar', x: 'category', y: 'count' }

    const { container } = render(<Charts chartSpec={spec} table={table} />)

    expect(screen.queryByText(FALLBACK)).not.toBeInTheDocument()
    expect(container.querySelectorAll('.recharts-bar-rectangle').length).toBeGreaterThan(0)
  })
})
