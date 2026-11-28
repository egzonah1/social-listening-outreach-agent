import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircle2,
  Inbox,
  MessageSquareReply,
  Newspaper,
  Play,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CampaignForm } from '../components/CampaignForm'
import { LifeEventChart } from '../components/LifeEventChart'
import { OverviewSkeleton } from '../components/Skeletons'
import { Badge, Button, Card, ErrorBox, StatTile } from '../components/ui'
import { api } from '../lib/api'
import { timeAgo } from '../lib/format'
import { LIFE_EVENTS, PLATFORMS } from '../lib/labels'
import { isActive } from '../lib/run'
import type { CampaignSummary } from '../lib/types'

const STEPS = [
  {
    icon: Search,
    title: '1. Find',
    text: 'Search public posts from official APIs for the keywords of a life event.',
  },
  {
    icon: Sparkles,
    title: '2. Sort and draft',
    text: 'Each post is scored and checked for sensitivity, and reply drafts are prepared.',
  },
  {
    icon: ShieldCheck,
    title: '3. You decide',
    text: 'Edit and approve a reply, then post it yourself. Nothing is sent automatically.',
  },
]

export function CampaignsPage() {
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const overview = useQuery({
    queryKey: ['overview'],
    queryFn: api.overview,
    staleTime: 0, // numbers change on other pages, so refresh on every visit
    // Keep the numbers fresh while any search is still running.
    refetchInterval: (query) =>
      query.state.data?.campaigns.some((c) => isActive(c.last_run ?? undefined)) ? 3000 : false,
  })
  const create = useMutation({
    mutationFn: api.createCampaign,
    onSuccess: (campaign) => {
      void queryClient.invalidateQueries({ queryKey: ['overview'] })
      navigate(`/campaigns/${campaign.id}`)
    },
  })

  const data = overview.data
  const empty = data?.campaigns.length === 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
          <p className="mt-1 text-sm text-slate-500">
            Find people talking about big life moments, and answer them with care.
          </p>
        </div>
        {!creating && (
          <Button icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
            New campaign
          </Button>
        )}
      </div>

      <ol className="grid gap-3 sm:grid-cols-3">
        {STEPS.map(({ icon: Icon, title, text }) => (
          <li key={title} className="flex gap-3 rounded-xl bg-white p-4 ring-1 ring-slate-200">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-700">
              <Icon className="size-4.5" aria-hidden />
            </span>
            <div>
              <p className="text-sm font-semibold text-slate-900">{title}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{text}</p>
            </div>
          </li>
        ))}
      </ol>

      {creating && (
        <Card className="p-5">
          <h2 className="mb-4 text-base font-semibold">New campaign</h2>
          <CampaignForm
            submitting={create.isPending}
            error={create.error}
            onCancel={() => setCreating(false)}
            onSubmit={(input) => create.mutate(input)}
          />
        </Card>
      )}

      {overview.isPending && <OverviewSkeleton />}
      {overview.isError && (
        <ErrorBox error={overview.error} onRetry={() => void overview.refetch()} />
      )}

      {data && !empty && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile icon={<Newspaper className="size-3.5" />} label="Posts collected" value={data.totals.posts} />
          <StatTile
            icon={<Inbox className="size-3.5" />}
            label="Waiting for review"
            value={data.totals.to_review}
            highlight
          />
          <StatTile icon={<CheckCircle2 className="size-3.5" />} label="Approved replies" value={data.totals.approved} />
          <StatTile
            icon={<MessageSquareReply className="size-3.5" />}
            label="Replied"
            value={data.totals.replied}
          />
        </div>
      )}

      {empty && !creating && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <h2 className="text-base font-semibold text-slate-900">Start your first campaign</h2>
          <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">
            Pick a life event such as "New baby" and we'll suggest keywords. Try "Sample data" as
            the source for a quick, reliable first run.
          </p>
          <Button className="mt-4" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
            Create a campaign
          </Button>
        </div>
      )}

      {data && !empty && <LifeEventChart data={data.life_events} />}

      {data && !empty && (
        <section className="space-y-3">
          <h2 className="text-base font-semibold">Campaigns ({data.campaigns.length})</h2>
          <ul className="grid gap-3 lg:grid-cols-2">
            {data.campaigns.map((summary) => (
              <CampaignCard key={summary.campaign.id} summary={summary} />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function CampaignCard({ summary }: { summary: CampaignSummary }) {
  const { campaign, last_run: run } = summary
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const running = isActive(run ?? undefined)
  const start = useMutation({
    mutationFn: () => api.startRun(campaign.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['runs', campaign.id] })
      navigate(`/campaigns/${campaign.id}`)
    },
  })

  return (
    <li>
      <Card className="flex h-full flex-col p-4 transition hover:ring-brand-600/50">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Link
              to={`/campaigns/${campaign.id}`}
              className="font-semibold text-slate-900 hover:text-brand-700"
            >
              {campaign.name}
            </Link>
            <p className="mt-0.5 truncate text-sm text-slate-500">{campaign.keywords.join(' · ')}</p>
          </div>
          <div className="flex shrink-0 flex-wrap justify-end gap-1">
            {campaign.life_events.map((event) => (
              <Badge key={event} tone="brand">
                {LIFE_EVENTS[event]}
              </Badge>
            ))}
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-3 gap-2 rounded-lg bg-slate-50 p-3 text-center">
          <Mini label="Posts" value={summary.posts} />
          <Mini label="To review" value={summary.to_review} strong={summary.to_review > 0} />
          <Mini label="Approved" value={summary.approved + summary.replied} />
        </dl>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <p className="flex items-center gap-1.5 text-xs text-slate-500">
            <span
              className={
                running
                  ? 'size-2 animate-pulse rounded-full bg-amber-500'
                  : run?.status === 'failed'
                    ? 'size-2 rounded-full bg-red-500'
                    : run
                      ? 'size-2 rounded-full bg-emerald-500'
                      : 'size-2 rounded-full bg-slate-300'
              }
              aria-hidden
            />
            {running
              ? 'Searching now…'
              : run
                ? `Last search ${timeAgo(run.finished_at ?? run.created_at)}`
                : 'Not searched yet'}
            <span className="text-slate-300">·</span>
            {campaign.sources.map((s) => PLATFORMS[s]).join(', ')}
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              icon={<Play className="size-3.5" />}
              loading={start.isPending}
              disabled={running}
              onClick={() => start.mutate()}
            >
              Run search
            </Button>
            <Link
              to={`/campaigns/${campaign.id}`}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-700 px-2.5 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-brand-800"
            >
              <Inbox className="size-3.5" aria-hidden />
              Open inbox
            </Link>
          </div>
        </div>
        {start.isError && (
          <div className="mt-3">
            <ErrorBox error={start.error} />
          </div>
        )}
      </Card>
    </li>
  )
}

function Mini({ label, value, strong = false }: { label: string; value: number; strong?: boolean }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className={strong ? 'text-lg font-semibold text-brand-700' : 'text-lg font-semibold text-slate-800'}>
        {value}
      </dd>
    </div>
  )
}
