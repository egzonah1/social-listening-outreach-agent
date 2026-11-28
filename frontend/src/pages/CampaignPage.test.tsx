import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CampaignPage } from './CampaignPage'

const campaign = {
  id: 3,
  name: 'Test 2026',
  description: null,
  keywords: ['launched my business'],
  life_events: ['new_business'],
  sources: ['bluesky'],
  language: 'en',
  created_at: '2026-11-28T09:00:00Z',
  updated_at: '2026-11-28T09:00:00Z',
}
const stats = { total_posts: 149, by_status: {}, by_life_event: {}, by_recommendation: {} }

function respond(body: unknown, status = 200) {
  return Promise.resolve(new Response(status === 204 ? null : JSON.stringify(body), { status }))
}

afterEach(() => vi.unstubAllGlobals())

describe('CampaignPage', () => {
  it('deletes the campaign only after confirming, then goes home', async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === 'DELETE') return respond(null, 204)
      if (url.endsWith('/campaigns/3')) return respond(campaign)
      if (url.includes('/runs')) return respond([])
      if (url.includes('/stats')) return respond(stats)
      return respond({ items: [], total: 0 })
    })
    vi.stubGlobal('fetch', fetchMock)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/campaigns/3']}>
          <Routes>
            <Route path="/" element={<p>Home page</p>} />
            <Route path="/campaigns/:campaignId" element={<CampaignPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Delete campaign' }))
    expect(await screen.findByText(/Delete "Test 2026" and its 149 posts\?/)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/campaigns/3', expect.objectContaining({ method: 'DELETE' }))

    await user.click(screen.getByRole('button', { name: 'Yes, delete campaign' }))

    expect(await screen.findByText('Home page')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/campaigns/3', expect.objectContaining({ method: 'DELETE' }))
  })
})
