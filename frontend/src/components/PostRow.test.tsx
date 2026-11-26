import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { Post } from '../lib/types'
import { PostRow } from './PostRow'

const post: Post = {
  id: 5,
  campaign_id: 1,
  platform: 'sample',
  url: 'sample://posts/5',
  author_handle: 'someone',
  author_display_name: null,
  text: 'My dad passed away on Sunday.',
  language: 'en',
  posted_at: '2026-11-25T10:00:00Z',
  like_count: 0,
  reply_count: 0,
  repost_count: 0,
  matched_keyword: '#grief',
  is_sample: true,
  status: 'new',
  analysis: {
    relevance: 60,
    life_event: 'bereavement',
    sensitivity: 'high',
    recommendation: 'supportive_only',
    reason: 'Backup rules (AI unavailable): a loss: kindness only.',
    summary: 'A recent loss.',
    model: 'rules',
  },
}

describe('PostRow', () => {
  it('labels sample data, sensitivity and backup-rule decisions clearly', () => {
    render(
      <MemoryRouter>
        <PostRow post={post} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link')).toHaveAttribute('href', '/posts/5')
    expect(screen.getByText('Supportive only')).toBeInTheDocument()
    expect(screen.getByText('High sensitivity')).toBeInTheDocument()
    expect(screen.getByText('Backup rules')).toBeInTheDocument()
    expect(screen.getByText('Sample')).toBeInTheDocument()
  })
})
