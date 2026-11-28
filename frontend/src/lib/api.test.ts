import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), { status }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('builds the inbox query and skips empty filters', async () => {
    const fetchMock = mockFetch(200, { items: [], total: 0 })

    await api.posts(7, { life_event: '', sort: 'newest', include_do_not_contact: true }, 20, 40)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/campaigns/7/posts?sort=newest&include_do_not_contact=true&limit=20&offset=40',
      expect.anything(),
    )
  })

  it("turns the server's message into an ApiError", async () => {
    mockFetch(410, { detail: 'The author removed this post, so its data has been deleted from the app.' })

    const error = await api.post(1).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(410)
    expect((error as ApiError).message).toMatch(/author removed this post/)
  })

  it('explains validation errors field by field', async () => {
    mockFetch(422, { detail: [{ loc: ['body', 'keywords'], msg: 'List should have at least 1 item' }] })

    await expect(
      api.createCampaign({ name: 'x', keywords: [], life_events: [], sources: ['sample'], language: 'en' }),
    ).rejects.toThrow('keywords: List should have at least 1 item')
  })

  it('says clearly when the backend cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(api.campaigns()).rejects.toThrow(/Cannot reach the server/)
  })

  it('handles 204 No Content', async () => {
    mockFetch(204, undefined)

    await expect(api.deletePost(3)).resolves.toBeUndefined()
  })
})

describe('api.exportApproved', () => {
  it('downloads the CSV with the name the server gives', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response('post_url\n', {
          status: 200,
          headers: { 'Content-Disposition': 'attachment; filename="approved-replies-campaign-7.csv"' },
        }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    await api.exportApproved(7)

    expect(fetchMock).toHaveBeenCalledWith('/api/campaigns/7/export.csv', expect.anything())
    const link = click.mock.instances[0] as unknown as HTMLAnchorElement
    expect(link.download).toBe('approved-replies-campaign-7.csv')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:x')
  })

  it('turns a server error into a readable message', async () => {
    vi.stubGlobal('fetch', () => Promise.resolve(new Response(JSON.stringify({ detail: 'Campaign not found' }), { status: 404 })))
    await expect(api.exportApproved(1)).rejects.toThrow('Campaign not found')
  })
})
