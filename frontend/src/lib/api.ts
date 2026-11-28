// The one place that talks to the backend. Every call is typed, and every
// error becomes an ApiError with the server's own message, so screens can
// show "The author removed this post" instead of "Request failed".

import { announceAccessDenied, clearAccessCode, getAccessCode } from './access'
import type {
  Campaign,
  CampaignInput,
  CampaignStats,
  Draft,
  Meta,
  Overview,
  PostDetail,
  PostFilters,
  PostPage,
  SearchRun,
} from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  const code = getAccessCode()
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(code ? { 'X-Access-Code': code } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is the backend running?')
  }
  if (response.status === 204) return undefined as T
  const body: unknown = await response.json().catch(() => null)
  if (response.status === 401) {
    // Missing or wrong access code: forget it and show the access screen.
    clearAccessCode()
    announceAccessDenied()
  }
  if (!response.ok) throw new ApiError(response.status, errorMessage(body, response.status))
  return body as T
}

function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc: [...], msg: "..."}]
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${d.loc?.slice(1).join('.') ?? ''}: ${d.msg}`)
      .join('; ')
  }
  return `Something went wrong (${status}).`
}

const json = (data: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(data) })

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  meta: () => request<Meta>('/meta'),

  overview: () => request<Overview>('/overview'),
  campaigns: () => request<Campaign[]>('/campaigns'),
  campaign: (id: number) => request<Campaign>(`/campaigns/${id}`),
  createCampaign: (input: CampaignInput) => request<Campaign>('/campaigns', json(input)),
  deleteCampaign: (id: number) => request<void>(`/campaigns/${id}`, { method: 'DELETE' }),

  startRun: (campaignId: number) =>
    request<SearchRun>(`/campaigns/${campaignId}/runs`, { method: 'POST' }),
  runs: (campaignId: number) => request<SearchRun[]>(`/campaigns/${campaignId}/runs`),
  run: (runId: number) => request<SearchRun>(`/runs/${runId}`),

  posts: (campaignId: number, filters: PostFilters, limit = 50, offset = 0) =>
    request<PostPage>(`/campaigns/${campaignId}/posts${query({ ...filters, limit, offset })}`),
  stats: (campaignId: number) => request<CampaignStats>(`/campaigns/${campaignId}/stats`),

  post: (id: number) => request<PostDetail>(`/posts/${id}`),
  generateDrafts: (id: number, instruction?: string) =>
    request<PostDetail>(`/posts/${id}/drafts`, json({ instruction: instruction || null })),
  markReplied: (id: number) => request<PostDetail>(`/posts/${id}/replied`, { method: 'POST' }),
  dismiss: (id: number) => request<PostDetail>(`/posts/${id}/dismiss`, { method: 'POST' }),
  deletePost: (id: number) => request<void>(`/posts/${id}`, { method: 'DELETE' }),

  updateDraft: (id: number, text: string) =>
    request<Draft>(`/drafts/${id}`, { method: 'PATCH', body: JSON.stringify({ text }) }),
  approveDraft: (id: number) => request<Draft>(`/drafts/${id}/approve`, { method: 'POST' }),
  rejectDraft: (id: number) => request<Draft>(`/drafts/${id}/reject`, { method: 'POST' }),
}
