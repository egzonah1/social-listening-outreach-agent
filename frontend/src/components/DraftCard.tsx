import clsx from 'clsx'
import { AlertTriangle, Check, Copy, X } from 'lucide-react'
import { useState } from 'react'
import { Badge, Button } from './ui'
import type { Draft } from '../lib/types'

interface Props {
  draft: Draft
  limit: number
  busy: boolean
  onSave: (text: string) => Promise<unknown>
  onApprove: () => void
  onReject: () => void
}

/**
 * One suggested reply. The person can edit it; the server re-runs the
 * guardrail checks on every save and returns fresh warnings.
 */
export function DraftCard({ draft, limit, busy, onSave, onApprove, onReject }: Props) {
  const [text, setText] = useState(draft.text)
  const [copied, setCopied] = useState(false)
  const editable = draft.status === 'suggested'
  const dirty = text !== draft.text
  const tooLong = text.length > limit

  async function approve() {
    if (dirty) await onSave(text) // never approve text the server hasn't checked
    onApprove()
  }

  async function copy() {
    await navigator.clipboard.writeText(draft.text)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  return (
    <article
      className={clsx(
        'rounded-xl bg-white p-4 shadow-sm ring-1',
        draft.status === 'approved' ? 'ring-emerald-300' : 'ring-slate-200',
        draft.status === 'rejected' && 'opacity-60',
      )}
    >
      <header className="mb-2 flex items-center gap-2">
        <h3 className="text-sm font-semibold capitalize">{draft.tone}</h3>
        {draft.status === 'approved' && <Badge tone="green">Approved</Badge>}
        {draft.status === 'rejected' && <Badge>Rejected</Badge>}
        {draft.text !== draft.original_text && <Badge tone="blue">Edited by a person</Badge>}
        <span
          className={clsx('ml-auto text-xs tabular-nums', tooLong ? 'text-red-700' : 'text-slate-500')}
        >
          {text.length}/{limit}
        </span>
      </header>

      {editable ? (
        <textarea
          aria-label={`${draft.tone} reply`}
          className="block min-h-24 w-full resize-y rounded-lg border-0 p-2.5 text-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-brand-600"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      ) : (
        <p className="whitespace-pre-wrap rounded-lg bg-slate-50 p-2.5 text-sm">{draft.text}</p>
      )}

      {draft.warnings.length > 0 && (
        <ul className="mt-2 space-y-1" aria-label="Guardrail warnings">
          {draft.warnings.map((warning) => (
            <li key={warning} className="flex items-start gap-1.5 text-xs text-amber-800">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              {warning}
            </li>
          ))}
        </ul>
      )}
      {dirty && (
        <p className="mt-2 text-xs text-slate-500">Unsaved edit: warnings update when you save.</p>
      )}

      <footer className="mt-3 flex flex-wrap gap-2">
        {editable && (
          <>
            <Button size="sm" icon={<Check className="size-3.5" />} loading={busy} onClick={() => void approve()} disabled={tooLong || !text.trim()}>
              Approve
            </Button>
            {dirty && (
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => void onSave(text)}>
                Save edit
              </Button>
            )}
            <Button size="sm" variant="ghost" icon={<X className="size-3.5" />} disabled={busy} onClick={onReject}>
              Reject
            </Button>
          </>
        )}
        {draft.status === 'approved' && (
          <Button size="sm" variant="secondary" icon={<Copy className="size-3.5" />} onClick={() => void copy()}>
            {copied ? 'Copied' : 'Copy text'}
          </Button>
        )}
      </footer>
    </article>
  )
}
