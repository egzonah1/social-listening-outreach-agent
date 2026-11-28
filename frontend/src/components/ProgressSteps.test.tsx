import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { PostDetail } from '../lib/types'
import { stepsDone } from '../lib/progress'
import { ProgressSteps } from './ProgressSteps'

const base = {
  id: 1,
  campaign_id: 1,
  platform: 'sample',
  url: 'sample://1',
  author_handle: 'a',
  author_display_name: null,
  text: 't',
  language: 'en',
  posted_at: '2026-11-25T10:00:00Z',
  like_count: 0,
  reply_count: 0,
  repost_count: 0,
  matched_keyword: null,
  is_sample: true,
  status: 'new',
  analysis: null,
  drafts: [],
  audit: [],
} as unknown as PostDetail

const analysis = {
  relevance: 80,
  life_event: 'new_baby',
  sensitivity: 'low',
  recommendation: 'engage',
  reason: 'r',
  summary: 's',
  model: 'gemini',
} as const

describe('ProgressSteps', () => {
  it('counts the steps a post has reached', () => {
    expect(stepsDone(base)).toBe(1)
    expect(stepsDone({ ...base, analysis })).toBe(2)
    const draft = { id: 1, status: 'suggested' } as PostDetail['drafts'][number]
    expect(stepsDone({ ...base, analysis, drafts: [draft] })).toBe(3)
    expect(stepsDone({ ...base, analysis, drafts: [{ ...draft, status: 'approved' }] })).toBe(4)
    expect(stepsDone({ ...base, analysis, status: 'replied' })).toBe(5)
  })

  it('stops at "Do not contact" for posts that must not be contacted', () => {
    render(<ProgressSteps post={{ ...base, analysis: { ...analysis, recommendation: 'do_not_contact' } }} />)
    expect(screen.getByText('Do not contact')).toBeInTheDocument()
    expect(screen.queryByText('Approved')).not.toBeInTheDocument()
  })
})
