'use client'

import { useState } from 'react'

interface QuestionInputProps {
  onSubmit: (question: string) => void
  disabled: boolean
  busy: boolean
}

export function QuestionInput({ onSubmit, disabled, busy }: QuestionInputProps) {
  const [value, setValue] = useState('')
  const canSend = !disabled && !busy && value.trim().length > 0

  function submit() {
    if (!canSend) return
    onSubmit(value.trim())
    setValue('')
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      className="flex items-end gap-2 rounded-xl border border-gray-200 bg-white p-2 shadow-sm"
    >
      <textarea
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
        disabled={disabled}
        placeholder={
          disabled ? 'Upload a CSV first…' : 'Ask a question about your data…'
        }
        className="max-h-40 min-h-[2.5rem] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none disabled:cursor-not-allowed"
      />
      <button
        type="submit"
        disabled={!canSend}
        className="shrink-0 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy ? 'Asking…' : 'Ask'}
      </button>
    </form>
  )
}
