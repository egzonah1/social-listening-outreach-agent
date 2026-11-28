import { LIFE_EVENTS } from '../lib/labels'
import type { LifeEvent } from '../lib/types'
import { Card } from './ui'

interface Props {
  data: { life_event: LifeEvent; posts: number }[]
}

/**
 * Horizontal bars: one measure (posts) across a few categories, already sorted.
 * Plain HTML instead of a chart library: five bars don't need 100 kB of code,
 * and a list is read correctly by screen readers.
 */
export function LifeEventChart({ data }: Props) {
  if (data.length === 0) return null
  const max = Math.max(...data.map((d) => d.posts))
  const total = data.reduce((sum, d) => sum + d.posts, 0)

  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold text-slate-900">What people are sharing</h2>
      <p className="mt-0.5 text-xs text-slate-500">Sorted posts by life event, all campaigns</p>
      <ul className="mt-4 space-y-2.5" aria-label="Posts by life event">
        {data.map((d) => {
          const share = Math.round((d.posts / total) * 100)
          return (
            <li
              key={d.life_event}
              className="group grid grid-cols-[7.5rem_1fr_3.5rem] items-center gap-3 text-sm"
              title={`${LIFE_EVENTS[d.life_event]}: ${d.posts} posts (${share}%)`}
            >
              <span className="truncate text-slate-600">{LIFE_EVENTS[d.life_event]}</span>
              <span className="h-2.5 rounded-full bg-slate-100" aria-hidden>
                <span
                  className="block h-full rounded-full bg-brand-600 transition-colors group-hover:bg-brand-700"
                  style={{ width: `${Math.max(2, (d.posts / max) * 100)}%` }}
                />
              </span>
              <span className="text-right tabular-nums text-slate-700">
                {d.posts}
                <span className="sr-only"> posts</span>
              </span>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
