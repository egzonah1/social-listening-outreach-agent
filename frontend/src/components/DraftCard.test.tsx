import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Draft } from '../lib/types'
import { DraftCard } from './DraftCard'

const draft: Draft = {
  id: 1,
  tone: 'warm',
  text: 'Congratulations on the new baby!',
  original_text: 'Congratulations on the new baby!',
  status: 'suggested',
  warnings: ['Mentions insurance without saying you work in it.'],
  approved_at: null,
  created_at: '2026-11-26T10:00:00Z',
  updated_at: '2026-11-26T10:00:00Z',
}

describe('DraftCard', () => {
  it('shows guardrail warnings and the character count', () => {
    render(<DraftCard draft={draft} limit={300} busy={false} onSave={vi.fn()} onApprove={vi.fn()} onReject={vi.fn()} />)

    expect(screen.getByText(/without saying you work in it/)).toBeInTheDocument()
    expect(screen.getByText('32/300')).toBeInTheDocument()
  })

  it('saves an edit before approving it', async () => {
    const calls: string[] = []
    const onSave = vi.fn(async () => calls.push('save'))
    const onApprove = vi.fn(() => calls.push('approve'))
    const user = userEvent.setup()
    render(<DraftCard draft={draft} limit={300} busy={false} onSave={onSave} onApprove={onApprove} onReject={vi.fn()} />)

    await user.type(screen.getByLabelText('warm reply'), ' 🎉')
    await user.click(screen.getByRole('button', { name: 'Approve' }))

    expect(onSave).toHaveBeenCalledWith('Congratulations on the new baby! 🎉')
    expect(calls).toEqual(['save', 'approve'])
  })

  it('blocks approving a reply that is too long for the platform', async () => {
    const user = userEvent.setup()
    render(<DraftCard draft={draft} limit={10} busy={false} onSave={vi.fn()} onApprove={vi.fn()} onReject={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled()
    await user.clear(screen.getByLabelText('warm reply'))
    await user.type(screen.getByLabelText('warm reply'), 'Congrats!')
    expect(screen.getByRole('button', { name: 'Approve' })).toBeEnabled()
  })

  it('cannot edit a draft that was already approved', () => {
    render(
      <DraftCard draft={{ ...draft, status: 'approved' }} limit={300} busy={false} onSave={vi.fn()} onApprove={vi.fn()} onReject={vi.fn()} />,
    )

    expect(screen.queryByLabelText('warm reply')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copy text' })).toBeInTheDocument()
  })
})
