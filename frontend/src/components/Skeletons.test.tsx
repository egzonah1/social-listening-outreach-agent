import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OverviewSkeleton, PostListSkeleton, PostPageSkeleton } from './Skeletons'

describe('Skeletons', () => {
  it('tell screen readers what is loading', () => {
    render(
      <>
        <OverviewSkeleton />
        <PostListSkeleton rows={2} />
        <PostPageSkeleton />
      </>,
    )
    expect(screen.getByRole('status', { name: 'Loading overview…' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Loading posts…' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Loading post…' })).toBeInTheDocument()
  })

  it('draws one placeholder row per expected post', () => {
    render(<PostListSkeleton rows={3} />)
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
  })
})
