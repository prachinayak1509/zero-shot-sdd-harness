'use client'

import { useEffect, useRef, useState } from 'react'
import type { ChatTurn } from '@/lib/types'
import { AnswerBlock } from './AnswerBlock'

interface ChatTranscriptProps {
  turns: ChatTurn[]
  hasDataset: boolean
  onAskFollowUp: (question: string) => void
  asking: boolean
}

export function ChatTranscript({ turns, hasDataset, onAskFollowUp, asking }: ChatTranscriptProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns])

  if (turns.length === 0) {
    return (
      <div className="flex h-full min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-white/50 p-8 text-center">
        <p className="text-sm font-medium text-gray-500">
          {hasDataset ? 'Ask your first question' : 'Upload a CSV to get started'}
        </p>
        <p className="mt-1 text-xs text-gray-400">
          {hasDataset
            ? 'e.g. “What is the average value per category?”'
            : 'Your conversation will appear here.'}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {turns.map((turn) => (
        <div key={turn.id} className="space-y-2">
          {/* User question */}
          <div className="flex justify-end">
            <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-blue-600 px-4 py-2 text-sm text-white shadow-sm">
              {turn.question}
            </div>
          </div>

          {/* Assistant turn */}
          <div className="flex justify-start">
            <div className="w-full max-w-[95%] rounded-2xl rounded-bl-sm border border-gray-200 bg-white px-4 py-3 shadow-sm">
              {turn.pending && <ThinkingIndicator />}
              {turn.error && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  <p className="font-medium">The model was unavailable.</p>
                  <p className="mt-1 text-red-600">{turn.error}</p>
                  <p className="mt-1 text-xs text-red-500">Please retry your question.</p>
                </div>
              )}
              {turn.result && (
                <AnswerBlock
                  result={turn.result}
                  onAskFollowUp={onAskFollowUp}
                  followUpsDisabled={asking}
                />
              )}
            </div>
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  )
}

/** "Thinking…" indicator with a live, incrementing step counter. */
function ThinkingIndicator() {
  const [step, setStep] = useState(1)
  useEffect(() => {
    const t = setInterval(() => setStep((s) => s + 1), 1200)
    return () => clearInterval(t)
  }, [])
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500">
      <span className="flex gap-1">
        <Dot delay="0ms" />
        <Dot delay="150ms" />
        <Dot delay="300ms" />
      </span>
      <span>Thinking… (step {step})</span>
    </div>
  )
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-blue-400"
      style={{ animationDelay: delay }}
    />
  )
}
