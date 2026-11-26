import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CampaignForm } from './CampaignForm'

function setup() {
  const onSubmit = vi.fn()
  render(<CampaignForm onSubmit={onSubmit} onCancel={() => {}} submitting={false} error={null} />)
  return { onSubmit, user: userEvent.setup() }
}

describe('CampaignForm', () => {
  it('shows what is missing instead of submitting an empty form', async () => {
    const { onSubmit, user } = setup()

    await user.click(screen.getByRole('button', { name: 'Create campaign' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText('Give the campaign a name.')).toBeInTheDocument()
    expect(screen.getByText('Add at least one keyword.')).toBeInTheDocument()
  })

  it('suggests keywords for a life event and submits a valid campaign', async () => {
    const { onSubmit, user } = setup()

    await user.type(screen.getByLabelText('Campaign name'), 'New parents')
    await user.click(screen.getByRole('button', { name: 'New baby' }))
    await user.type(screen.getByLabelText(/Keywords and hashtags/), '#babyboy{Enter}')
    await user.click(screen.getByRole('button', { name: 'Remove first baby' }))
    await user.click(screen.getByRole('button', { name: 'Create campaign' }))

    expect(onSubmit).toHaveBeenCalledWith({
      name: 'New parents',
      keywords: ['new baby', 'baby arrived', '#newborn', '#babyboy'],
      life_events: ['new_baby'],
      sources: ['bluesky'],
      language: 'en',
    })
  })
})
