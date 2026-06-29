// Thin API client. Calls the same-origin FastAPI backend at /api/...
// Every success response is the ok(data) envelope: { data, error: null }.
// Every error is { detail: { code, message } } with a non-2xx status.
// Each function unwraps `data` and throws an ApiError carrying detail.message.

import type { AskResult, Dataset } from './types'

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
