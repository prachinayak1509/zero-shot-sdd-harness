// Thin API client. Calls the same-origin FastAPI backend at /api/...
// Every success response is the ok(data) envelope: { data, error: null }.
// Every error is { detail: { code, message } } with a non-2xx status.
// Each function unwraps `data` and throws an ApiError carrying detail.message.

import type {
  AskResult,
  Conversation,
  Dataset,
  DerivedDataset,
  SessionSummary,
} from './types'

export class ApiError extends Error {
  code: string
  status: number
  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

interface Envelope<T> {
  data: T
  error: string | null
}

interface DetailBody {
  detail?: { code?: string; message?: string }
}

async function unwrap<T>(res: Response): Promise<T> {
  let body: unknown
  try {
    body = await res.json()
  } catch {
    if (!res.ok) {
      throw new ApiError(`Request failed (${res.status})`, 'http_error', res.status)
    }
    throw new ApiError('Malformed server response', 'bad_response', res.status)
  }

  if (!res.ok) {
    const detail = (body as DetailBody).detail
    const message = detail?.message ?? `Request failed (${res.status})`
    const code = detail?.code ?? 'http_error'
    throw new ApiError(message, code, res.status)
  }

  return (body as Envelope<T>).data
}

/** Upload one CSV (multipart, field name `file`) and get back its profile. */
export async function uploadDataset(file: File): Promise<Dataset> {
  const form = new FormData()
  form.append('file', file)
  let res: Response
  try {
    res = await fetch('/api/datasets', { method: 'POST', body: form })
  } catch {
    throw new ApiError('Network error — is the server running?', 'network', 0)
  }
  return unwrap<Dataset>(res)
}

/** Re-fetch a dataset's stored profile (e.g. to render on reload). */
export async function getDataset(id: number): Promise<Dataset> {
  let res: Response
  try {
    res = await fetch(`/api/datasets/${id}`)
  } catch {
    throw new ApiError('Network error — is the server running?', 'network', 0)
  }
  return unwrap<Dataset>(res)
}

/**
 * Add one or more files (CSV or .xlsx) to a workspace. Each file — and each
 * sheet of a multi-sheet xlsx — becomes its own named Dataset table. When
 * `conversationId` is given the files are added to that existing conversation's
 * workspace (POST /api/datasets with the current `conversation_id`).
 *
 * The backend may return a single Dataset (one CSV) or a list (multi-file /
 * multi-sheet); this normalizes both to a Dataset[].
 */
export async function addFilesToWorkspace(
  files: File[],
  conversationId: number | null,
): Promise<Dataset[]> {
  const form = new FormData()
  for (const f of files) form.append('file', f)
  if (conversationId != null) form.append('conversation_id', String(conversationId))
  let res: Response
  try {
    res = await fetch('/api/datasets', { method: 'POST', body: form })
  } catch {
    throw new ApiError('Network error — is the server running?', 'network', 0)
  }
  const data = await unwrap<Dataset | Dataset[]>(res)
  return Array.isArray(data) ? data : [data]
}

/** List saved sessions for the sidebar (most-recent first per backend ordering). */
export async function listConversations(): Promise<SessionSummary[]> {
  let res: Response
  try {
    res = await fetch('/api/conversations')
  } catch {
    throw new ApiError('Network error — is the server running?', 'network', 0)
  }
  return unwrap<SessionSummary[]>(res)
}

/** Reload one conversation with its full message history, audits, and datasets. */
export async function getConversation(id: number): Promise<Conversation> {
  let res: Response
  try {
    res = await fetch(`/api/conversations/${id}`)
  } catch {
    throw new ApiError('Network error — is the server running?', 'network', 0)
  }
  return unwrap<Conversation>(res)
}

/** Save a cleaned/derived result as both a reusable file and a code recipe. */
export async function saveDerived(
  datasetId: number,
  name: string,
  code: string,
): Promise<DerivedDataset> {
  let res: Response
  try {
    res = await fetch(`/api/datasets/${datasetId}/derived`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, code }),
    })
  } catch {
    throw new ApiError('Network error — is the server running?', 'network', 0)
  }
  return unwrap<DerivedDataset>(res)
}

/** Ask one question against a dataset; conversationId continues a conversation. */
export async function askQuestion(
  id: number,
  question: string,
  conversationId: number | null,
): Promise<AskResult> {
  let res: Response
  try {
    res = await fetch(`/api/datasets/${id}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, conversation_id: conversationId }),
    })
  } catch {
    throw new ApiError('Network error — is the server running?', 'network', 0)
  }
  return unwrap<AskResult>(res)
}
