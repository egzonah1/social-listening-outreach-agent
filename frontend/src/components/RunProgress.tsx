import { CheckCircle2, CircleAlert, Loader2 } from 'lucide-react'
import { dateTime } from '../lib/format'
import { PLATFORMS } from '../lib/labels'
import { isActive } from '../lib/run'
import type { Platform, SearchRun } from '../lib/types'
import { Card } from './ui'

/** Shows what a search run is doing right now, step by step. */
export function RunProgress({ run }: { run: SearchRun }) {
  const active = isActive(run)
  const steps = [
    { label: 'Searching sources', value: `${run.posts_found} found, ${run.posts_new} new` },
    { label: 'AI sorting', value: `${run.posts_analyzed} analysed` },
    { label: 'Reply drafts prepared', value: `${run.posts_drafted} posts` },
  ]

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-2" aria-live="polite">
        {active ? (
          <Loader2 className="size-4 animate-spin text-brand-700" aria-hidden />
        ) : run.status === 'failed' ? (
          <CircleAlert className="size-4 text-red-600" aria-hidden />
        ) : (
          <CheckCircle2 className="size-4 text-emerald-600" aria-hidden />
        )}
        <h2 className="text-sm font-semibold">
          {run.status === 'queued' && 'Search queued…'}
          {run.status === 'running' && 'Search running… new posts appear below as they are sorted'}
          {run.status === 'completed' && 'Last search finished'}
          {run.status === 'failed' && 'Last search failed'}
        </h2>
        <span className="ml-auto text-xs text-slate-500">
          {run.finished_at ? dateTime(run.finished_at) : run.started_at && dateTime(run.started_at)}
        </span>
      </div>

      <dl className="mt-3 grid gap-2 sm:grid-cols-3">
        {steps.map((step) => (
          <div key={step.label} className="rounded-lg bg-slate-50 px-3 py-2">
            <dt className="text-xs text-slate-500">{step.label}</dt>
            <dd className="text-sm font-medium text-slate-900">{step.value}</dd>
          </div>
        ))}
      </dl>

      <ul className="mt-3 space-y-1 text-xs">
        {Object.entries(run.source_stats).map(([source, stat]) => (
          <li key={source} className={stat.error ? 'text-red-700' : 'text-slate-500'}>
            {PLATFORMS[source as Platform] ?? source}:{' '}
            {stat.error ? `failed: ${stat.error}` : `${stat.found} found, ${stat.new} new`}
          </li>
        ))}
        {run.error && <li className="text-red-700">{run.error}</li>}
        {run.triage_error && (
          <li className="text-amber-800">AI sorting problem: {run.triage_error}</li>
        )}
      </ul>
    </Card>
  )
}
