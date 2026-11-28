import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BlockedAuthorsPage } from './BlockedAuthorsPage'

function respond(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }))
}

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <BlockedAuthorsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return userEvent.setup()
}

afterEach(() => vi.unstubAllGlobals())

describe('BlockedAuthorsPage', () => {
  it('adds an author and says how many posts were deleted', async () => {
    const entry = {
      id: 1,
      platform: 'bluesky',
      author_handle: 'maya.bsky.social',
      reason: 'asked by email',
      created_at: '2026-11-28T09:00:00Z',
    }
    let listed: unknown[] = []
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        listed = [entry]
        return respond({ blocked: entry, posts_deleted: 2 }, 201)
      }
      return respond(listed)
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = setup()

    expect(await screen.findByText('Nobody on the list')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Handle'), '@maya.bsky.social')
    await user.type(screen.getByLabelText('Reason (optional)'), 'asked by email')
    await user.click(screen.getByRole('button', { name: 'Add to list' }))

    expect(await screen.findByText(/2 collected post\(s\) deleted/)).toBeInTheDocument()
    expect(await screen.findByText('@maya.bsky.social')).toBeInTheDocument()
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      platform: 'bluesky',
      author_handle: '@maya.bsky.social',
      reason: 'asked by email',
    })
  })
})
