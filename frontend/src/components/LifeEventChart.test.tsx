import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LifeEventChart } from './LifeEventChart'

describe('LifeEventChart', () => {
  it('shows one bar per life event with its count, longest for the most common', () => {
    render(
      <LifeEventChart
        data={[
          { life_event: 'new_baby', posts: 12 },
          { life_event: 'home_purchase', posts: 4 },
        ]}
      />,
    )
    const rows = within(screen.getByRole('list', { name: 'Posts by life event' })).getAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('New baby12 posts')
    expect(rows[0]).toHaveAttribute('title', 'New baby: 12 posts (75%)')
    const bars = rows.map((row) => row.querySelector<HTMLElement>('span span')?.style.width)
    expect(bars).toEqual(['100%', '33.3333%'])
  })

  it('renders nothing before any post is sorted', () => {
    const { container } = render(<LifeEventChart data={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
