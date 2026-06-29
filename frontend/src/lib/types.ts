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

/** One ordered step of an answer's trace (Phase 3). */
export interface Step {
  node: string
  code?: string | null
  result_repr?: string | null
  error?: string | null
  rationale?: string | null
  tokens?: number | null
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
  // Phase 3 — full ordered step trace ({node, code, rationale, tokens, ...}).
  steps?: Step[] | null
}

/** A saved session as shown in the sidebar list (Phase 3). */
export interface SessionSummary {
  id: number
  title: string | null
  dataset_id: number
  updated_at: string
}

/** The audit attached to an assistant message when a conversation is reloaded. */
export interface MessageAudit {
  audit_id: number
  answer: string
  code: string
  result_repr: string
  effort: string
  step_count: number
  status: 'completed' | 'failed' | string
  tokens_used: number
  chart_spec?: ChartSpec | null
  table?: ResultTable | null
  follow_ups?: string[] | null
  steps?: Step[] | null
}

/** One persisted message in a reloaded conversation (Phase 3). */
export interface ConversationMessage {
  id: number
  role: 'user' | 'assistant' | string
  content: string
  audit_id?: number | null
  audit?: MessageAudit | null
}

/** A reloaded conversation with its full history (Phase 3). */
export interface Conversation {
  id: number
  title: string | null
  dataset_id: number
  updated_at: string
  /** All datasets loaded into this workspace (one per file / xlsx sheet). */
  datasets?: Dataset[] | null
  messages: ConversationMessage[]
  /** Running session token total across every answered question. */
  session_tokens?: number | null
}

/** The result of saving a derived dataset (Phase 3). */
export interface DerivedDataset {
  id: number
  name: string
  file_path: string
  recipe: string
  row_count?: number
  profile?: Profile | null
}

/** A single turn in the chat transcript. */
export interface ChatTurn {
  id: string
  question: string
  result: AskResult | null
  error: string | null
  pending: boolean
}
