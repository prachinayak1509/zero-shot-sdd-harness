'use client'

import { useState } from 'react'
import { ApiError, askQuestion, uploadDataset } from '@/lib/api'
import type { ChatTurn, Dataset } from '@/lib/types'
import { Sidebar } from '@/components/Sidebar'
import { UploadDropzone } from '@/components/UploadDropzone'
import { ProfilePanel } from '@/components/ProfilePanel'
import { ChatTranscript } from '@/components/ChatTranscript'
import { QuestionInput } from '@/components/QuestionInput'
import { StubPanel } from '@/components/StubPanel'

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [asking, setAsking] = useState(false)

  async function handleUpload(file: File) {
    setUploading(true)
    setUploadError(null)
    try {
      const ds = await uploadDataset(file)
      setDataset(ds)
      // New dataset → fresh conversation + transcript.
      setTurns([])
      setConversationId(null)
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
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
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turnId ? { ...t, result, pending: false, error: null } : t,
        ),
      )
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Something went wrong.'
      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, pending: false, error: message } : t)),
      )
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />

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
          {/* Phase 3 stub: add file / sheet */}
          <StubPanel title="+ Add file / sheet" phase="Phase 3" className="hidden sm:block" />
        </header>

        <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-5 px-4 py-6 sm:px-6">
          {/* Upload */}
          <UploadDropzone
            onFile={handleUpload}
            uploading={uploading}
            error={uploadError}
            loadedName={dataset?.name ?? null}
          />

          {/* Profile (real data once uploaded) */}
          {dataset && <ProfilePanel dataset={dataset} />}

          {/* Chat transcript — charts / table / follow-ups render inside each answer */}
          <div className="flex-1">
            <ChatTranscript
              turns={turns}
              hasDataset={!!dataset}
              onAskFollowUp={handleAsk}
              asking={asking}
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
