import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { announceAccessDenied, getAccessCode } from '../lib/access'
import { AccessGate } from './AccessGate'

function renderGate(required: boolean) {
  const client = new QueryClient()
  return render(
    <QueryClientProvider client={client}>
      <AccessGate required={required}>
        <p>The app</p>
      </AccessGate>
    </QueryClientProvider>,
  )
}

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('AccessGate', () => {
  it('shows the app directly when no code is needed', () => {
    renderGate(false)
    expect(screen.getByText('The app')).toBeInTheDocument()
  })

  it('unlocks with the right code and sends it as a header', async () => {
    const fetchMock = mockFetch(200, [])
    renderGate(true)
    expect(screen.queryByText('The app')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Access code'), { target: { value: ' secret ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText('The app')).toBeInTheDocument()
    expect(getAccessCode()).toBe('secret')
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect((init.headers as Record<string, string>)['X-Access-Code']).toBe('secret')
  })

  it('explains a wrong code and forgets it', async () => {
    mockFetch(401, { detail: 'Wrong access code' })
    renderGate(true)

    fireEvent.change(screen.getByLabelText('Access code'), { target: { value: 'nope' } })
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText(/code is not right/)).toBeInTheDocument()
    expect(getAccessCode()).toBeNull()
  })

  it('locks again when the server refuses the saved code', async () => {
    localStorage.setItem('outreach.accessCode', 'old')
    renderGate(true)
    expect(screen.getByText('The app')).toBeInTheDocument()

    act(() => announceAccessDenied())

    await waitFor(() => expect(screen.queryByText('The app')).not.toBeInTheDocument())
    expect(screen.getByLabelText('Access code')).toBeInTheDocument()
  })
})
