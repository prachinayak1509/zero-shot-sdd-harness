// Shared types mirroring the spec/api.md response contract.

export interface ProfileColumn {
  name: string
  dtype: string
  min: string | number | null
  max: string | number | null
  null_count: number
  // Phase 2 — data-quality fields (deterministic, no LLM).
  null_pct?: number
  outlier_count?: number
  flags?: string[]
}

export interface ProfileQuality {
  total_flags: number
  notes: string[]
}

export interface Profile {
  columns: ProfileColumn[]
  row_count: number
  sample?: Record<string, unknown>[] | null
  // Phase 2 — root-level data-quality summary.
  quality?: ProfileQuality | null
}

/** Agent-chosen chart encoding (Phase 2). */
export interface ChartSpec {
  type: 'bar' | 'line' | 'scatter' | 'pie' | string
  x: string
  y: string
  series?: string | null
  title?: string | null
}

/** Aggregated result table the agent's code produced (Phase 2). */
export interface ResultTable {
  columns: string[]
  rows: unknown[][]
}

export interface Dataset {
  id: number
  name: string
  row_count: number
  profile: Profile
}

export interface AskResult {
  conversation_id: number
  audit_id: number
  answer: string
  code: string
  result_repr: string
  effort: string
  step_count: number
  status: 'completed' | 'failed' | string
  tokens_used: number
  // Phase 2 — populated by the rich-answer presentation pass.
  chart_spec?: ChartSpec | null
  table?: ResultTable | null
  follow_ups?: string[] | null
  // Phase 3 — full step trace.
  steps?: unknown[] | null
}

/** A single turn in the chat transcript. */
export interface ChatTurn {
  id: string
  question: string
  result: AskResult | null
  error: string | null
  pending: boolean
}
