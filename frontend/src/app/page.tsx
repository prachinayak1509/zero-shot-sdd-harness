'use client'

import { useEffect, useState } from 'react'
import {
  ApiError,
  addFilesToWorkspace,
  askQuestion,
  getConversation,
  getDataset,
  listConversations,
  uploadDataset,
} from '@/lib/api'
import type {
  AskResult,
  ChatTurn,
  Dataset,
  DerivedDataset,
  SessionSummary,
} from '@/lib/types'
import { SessionsSidebar } from '@/components/SessionsSidebar'
import { FileManager } from '@/components/FileManager'
import { UploadDropzone } from '@/components/UploadDropzone'
import { ProfilePanel } from '@/components/ProfilePanel'
import { ChatTranscript } from '@/components/ChatTranscript'
import { QuestionInput } from '@/components/QuestionInput'

export default function Home() {
  // Primary dataset (drives upload/profile/ask) plus every loaded workspace table.
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [asking, setAsking] = useState(false)

  // Phase 3 — saved sessions, extra-file management, token meter.
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [sessionsError, setSessionsError] = useState<string | null>(null)

  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  const [lastQuestionTokens, setLastQuestionTokens] = useState<number | null>(null)
  const [sessionTokens, setSessionTokens] = useState(0)

  async function refreshSessions() {
    setSessionsLoading(true)
    setSessionsError(null)
    try {
      const list = await listConversations()
      setSessions(list)
    } catch (err) {
      setSessionsError(
        err instanceof ApiError ? err.message : 'Could not load saved sessions.',
      )
    } finally {
      setSessionsLoading(false)
    }
  }

  // On mount: populate the sidebar. Tolerate failure — never crash the app.
  useEffect(() => {
    void refreshSessions()
  }, [])

  function handleNewSession() {
    setDataset(null)
    setDatasets([])
    setTurns([])
    setConversationId(null)
    setLastQuestionTokens(null)
    setSessionTokens(0)
    setUploadError(null)
    setAddError(null)
  }

  async function handleResume(id: number) {
    try {
      const conv = await getConversation(id)
      setConversationId(conv.id)

      // Load workspace tables — prefer the embedded list, else fetch the primary.
      let loaded: Dataset[] = conv.datasets ?? []
      if (loaded.length === 0) {
        try {
          const primary = await getDataset(conv.dataset_id)
          loaded = [primary]
        } catch {
          loaded = []
        }
      }
      setDatasets(loaded)
      setDataset(loaded[0] ?? null)

      // Rebuild the transcript: pair each user message with the following
      // assistant message's audit into an AskResult-shaped ChatTurn.
      const rebuilt: ChatTurn[] = []
      const msgs = conv.messages ?? []
      for (let i = 0; i < msgs.length; i++) {
        const msg = msgs[i]
        if (msg.role !== 'user') continue
        const next = msgs[i + 1]
        const audit =
          next && next.role === 'assistant' ? next.audit ?? null : null
        let result: AskResult | null = null
        if (audit) {
          result = {
            conversation_id: conv.id,
            audit_id: audit.audit_id,
            answer: audit.answer,
            code: audit.code,
            result_repr: audit.result_repr,
            effort: audit.effort,
            step_count: audit.step_count,
            status: audit.status,
            tokens_used: audit.tokens_used,
            chart_spec: audit.chart_spec ?? null,
            table: audit.table ?? null,
            follow_ups: audit.follow_ups ?? null,
            steps: audit.steps ?? null,
          }
        }
        rebuilt.push({
          id: `msg-${msg.id}`,
          question: msg.content,
          result,
          error: null,
          pending: false,
        })
      }
      setTurns(rebuilt)

      setSessionTokens(conv.session_tokens ?? 0)
      setLastQuestionTokens(null)
      setUploadError(null)
      setAddError(null)
    } catch (err) {
      setSessionsError(
        err instanceof ApiError ? err.message : 'Could not reopen that session.',
      )
    }
  }

  async function handleUpload(file: File) {
    setUploading(true)
    setUploadError(null)
    try {
      const ds = await uploadDataset(file)
      setDataset(ds)
      setDatasets([ds])
      // New dataset → fresh conversation + transcript.
      setTurns([])
      setConversationId(null)
      setLastQuestionTokens(null)
      setSessionTokens(0)
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  async function handleAddFiles(files: File[]) {
    setAdding(true)
    setAddError(null)
    try {
      const added = await addFilesToWorkspace(files, conversationId)
      setDatasets((prev) => [...prev, ...added])
      // Adopt the first loaded table as primary if none yet.
      setDataset((prev) => prev ?? added[0] ?? null)
    } catch (err) {
      setAddError(err instanceof ApiError ? err.message : 'Could not add files.')
    } finally {
      setAdding(false)
    }
  }

  async function handleAsk(question: string) {
    if (!dataset) return
    const turnId = `${Date.now()}-${Math.random().toString(36).slice(2)}`
    setTurns((prev) => [
      ...prev,
      { id: turnId, question, result: null, error: null, pending: true },
    ])
    setAsking(true)
    try {
      const result = await askQuestion(dataset.id, question, conversationId)
      setConversationId(result.conversation_id)
      setLastQuestionTokens(result.tokens_used)
      setSessionTokens((prev) => prev + result.tokens_used)
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turnId ? { ...t, result, pending: false, error: null } : t,
        ),
      )
      // A brand-new conversation should now appear in the sidebar.
      void refreshSessions()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Something went wrong.'
      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, pending: false, error: message } : t)),
      )
    } finally {
      setAsking(false)
    }
  }

  function handleSavedDerived(ds: DerivedDataset) {
    // The derived dataset becomes a new workspace table once saved.
    setDatasets((prev) => [
      ...prev,
      {
        id: ds.id,
        name: ds.name,
        row_count: ds.row_count ?? 0,
        profile: ds.profile ?? { columns: [], row_count: ds.row_count ?? 0 },
      },
    ])
  }

  return (
    <div className="flex min-h-screen">
      <SessionsSidebar
        sessions={sessions}
        loading={sessionsLoading}
        error={sessionsError}
        activeConversationId={conversationId}
        onResume={handleResume}
        onNewSession={handleNewSession}
        lastQuestionTokens={lastQuestionTokens}
        sessionTokens={sessionTokens}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-gray-200 bg-white/70 px-6 py-3 backdrop-blur">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-gray-900">
              Analysis Workspace
            </h1>
            <p className="text-xs text-gray-500">
              Upload a CSV, then ask questions in plain English.
            </p>
          </div>
        </header>

        <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-5 px-4 py-6 sm:px-6">
          {/* Upload */}
          <UploadDropzone
            onFile={handleUpload}
            uploading={uploading}
            error={uploadError}
            loadedName={dataset?.name ?? null}
          />

          {/* Workspace tables — add more files (CSV / xlsx sheets) to join/compare. */}
          {(dataset || datasets.length > 0) && (
            <FileManager
              datasets={datasets}
              onAddFiles={handleAddFiles}
              adding={adding}
              error={addError}
            />
          )}

          {/* Profile (real data once uploaded) */}
          {dataset && <ProfilePanel dataset={dataset} />}

          {/* Chat transcript — charts / table / trace / follow-ups render inside each answer */}
          <div className="flex-1">
            <ChatTranscript
              turns={turns}
              hasDataset={!!dataset}
              onAskFollowUp={handleAsk}
              asking={asking}
              datasetId={dataset?.id ?? null}
              onSavedDerived={handleSavedDerived}
            />
          </div>
        </main>

        {/* Question input pinned to bottom of the column */}
        <div className="sticky bottom-0 border-t border-gray-200 bg-white/80 px-4 py-3 backdrop-blur sm:px-6">
          <div className="mx-auto w-full max-w-4xl">
            <QuestionInput onSubmit={handleAsk} disabled={!dataset} busy={asking} />
          </div>
        </div>
      </div>
    </div>
  )
}
