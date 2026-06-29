// Shared types mirroring the spec/api.md response contract.

export interface ProfileColumn {
  name: string
  dtype: string
  min: string | number | null
  max: string | number | null
  null_count: number
}

export interface Profile {
  columns: ProfileColumn[]
  row_count: number
  sample?: Record<string, unknown>[] | null
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
  // Phase 2/3 — null in Phase 1, rendered as labelled stubs.
  chart_spec?: unknown | null
  table?: unknown | null
  follow_ups?: string[] | null
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
