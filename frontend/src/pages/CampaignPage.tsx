import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Download, Play, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { PostRow } from '../components/PostRow'
import { RunProgress } from '../components/RunProgress'
import { PostListSkeleton } from '../components/Skeletons'
import { Badge, Button, EmptyState, ErrorBox, Spinner, StatTile, selectClass } from '../components/ui'
import { api } from '../lib/api'
import { LIFE_EVENTS, PLATFORMS, POST_STATUS } from '../lib/labels'
import { isActive } from '../lib/run'
import type { LifeEvent, PostFilters, PostStatus } from '../lib/types'

const PAGE_SIZE = 20
const POLL_MS = 2000

export function CampaignPage() {
  const campaignId = Number(useParams().campaignId)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [filters, setFilters] = useState<PostFilters>({ sort: 'relevance' })
  const [page, setPage] = useState(0)

  const campaign = useQuery({
    queryKey: ['campaign', campaignId],
    queryFn: () => api.campaign(campaignId),
  })
  const runs = useQuery({
    queryKey: ['runs', campaignId],
    queryFn: () => api.runs(campaignId),
    // Poll while a search is running, so progress and new posts appear live.
    refetchInterval: (query) => (isActive(query.state.data?.[0]) ? POLL_MS : false),
  })
  const latestRun = runs.data?.[0]
  const running = isActive(latestRun)

  const posts = useQuery({
    queryKey: ['posts', campaignId, filters, page],
    queryFn: () => api.posts(campaignId, filters, PAGE_SIZE, page * PAGE_SIZE),
    placeholderData: keepPreviousData,
    refetchInterval: running ? POLL_MS : false,
  })
  const stats = useQuery({
    queryKey: ['stats', campaignId],
    queryFn: () => api.stats(campaignId),
    refetchInterval: running ? POLL_MS : false,
  })

  // When a run finishes, refresh everything once more.
  const finishedId = latestRun && !running ? latestRun.id : undefined
  useEffect(() => {
    if (finishedId === undefined) return
    void queryClient.invalidateQueries({ queryKey: ['posts', campaignId] })
    void queryClient.invalidateQueries({ queryKey: ['stats', campaignId] })
  }, [finishedId, campaignId, queryClient])

  const start = useMutation({
    mutationFn: () => api.startRun(campaignId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['runs', campaignId] }),
  })
  const exportCsv = useMutation({ mutationFn: () => api.exportApproved(campaignId) })
  const remove = useMutation({
    mutationFn: () => api.deleteCampaign(campaignId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['campaign', campaignId] })
      void queryClient.invalidateQueries({ queryKey: ['overview'] })
      navigate('/')
    },
  })

  function updateFilter(change: Partial<PostFilters>) {
    setFilters({ ...filters, ...change })
    setPage(0)
  }

  if (campaign.isPending) return <Spinner label="Loading campaign…" />
  if (campaign.isError) return <ErrorBox error={campaign.error} />
  const c = campaign.data
  const total = posts.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const s = stats.data
  const approvedCount = (s?.by_status.approved ?? 0) + (s?.by_status.replied ?? 0)

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900">
          <ArrowLeft className="size-4" /> Campaigns
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{c.name}</h1>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {c.keywords.map((k) => (
                <Badge key={k}>{k}</Badge>
              ))}
              {c.sources.map((source) => (
                <Badge key={source} tone="blue">
                  {PLATFORMS[source]}
                </Badge>
              ))}
            </div>
          </div>
          {confirmDelete ? (
            <div className="flex flex-wrap items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-900 ring-1 ring-red-200">
              Delete "{c.name}" and its {s?.total_posts ?? 0} posts? This can't be undone.
              <Button size="sm" variant="danger" loading={remove.isPending} onClick={() => remove.mutate()}>
                Yes, delete campaign
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button
                variant="ghost"
                icon={<Trash2 className="size-4" />}
                aria-label="Delete campaign"
                title="Delete campaign"
                onClick={() => setConfirmDelete(true)}
              />
              <Button
                variant="secondary"
                icon={<Download className="size-4" />}
                loading={exportCsv.isPending}
                disabled={approvedCount === 0}
                title={approvedCount === 0 ? 'Approve a reply first' : 'Approved replies as a spreadsheet (CSV)'}
                onClick={() => exportCsv.mutate()}
              >
                Export approved
              </Button>
              <Button
                icon={<Play className="size-4" />}
                loading={start.isPending || running}
                onClick={() => start.mutate()}
              >
                {running ? 'Searching…' : 'Run search'}
              </Button>
            </div>
          )}
        </div>
      </div>

      {start.isError && <ErrorBox error={start.error} />}
      {exportCsv.isError && <ErrorBox error={exportCsv.error} />}
      {remove.isError && <ErrorBox error={remove.error} />}
      {latestRun && <RunProgress run={latestRun} />}

      {s && s.total_posts > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="Posts collected" value={s.total_posts} />
          <StatTile label="Worth a reply" value={s.by_recommendation.engage ?? 0} />
          <StatTile label="Supportive only" value={s.by_recommendation.supportive_only ?? 0} />
          <StatTile label="Approved replies" value={approvedCount} />
        </div>
      )}

      <section className="space-y-3" aria-labelledby="inbox-title">
        <div className="flex flex-wrap items-end gap-3">
          <h2 id="inbox-title" className="mr-auto text-lg font-semibold">
            Review inbox <span className="text-sm font-normal text-slate-500">({total})</span>
          </h2>
          <select
            aria-label="Life event"
            className={selectClass}
            value={filters.life_event ?? ''}
            onChange={(e) => updateFilter({ life_event: e.target.value as LifeEvent | '' })}
          >
            <option value="">All life events</option>
            {Object.entries(LIFE_EVENTS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            aria-label="Status"
            className={selectClass}
            value={filters.status ?? ''}
            onChange={(e) => updateFilter({ status: e.target.value as PostStatus | '' })}
          >
            <option value="">Any status</option>
            {Object.entries(POST_STATUS).map(([value, { label }]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            aria-label="Sort"
            className={selectClass}
            value={filters.sort}
            onChange={(e) => updateFilter({ sort: e.target.value as 'relevance' | 'newest' })}
          >
            <option value="relevance">Most relevant first</option>
            <option value="newest">Newest first</option>
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              className="accent-brand-700"
              checked={filters.include_do_not_contact ?? false}
              onChange={(e) => updateFilter({ include_do_not_contact: e.target.checked })}
            />
            Show "do not contact"
          </label>
        </div>

        {posts.isPending && <PostListSkeleton />}
        {posts.isError && <ErrorBox error={posts.error} onRetry={() => void posts.refetch()} />}
        {posts.data?.items.length === 0 && (
          <EmptyState title={latestRun ? 'No posts match' : 'No posts yet'}>
            {latestRun
              ? 'Try other filters, or include "do not contact" posts.'
              : 'Run a search to collect public posts for this campaign.'}
          </EmptyState>
        )}
        <ul className="grid gap-3">
          {posts.data?.items.map((post) => (
            <li key={post.id}>
              <PostRow post={post} />
            </li>
          ))}
        </ul>

        {pages > 1 && (
          <nav className="flex items-center justify-between text-sm" aria-label="Pages">
            <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <span className="text-slate-500">
              Page {page + 1} of {pages}
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={page + 1 >= pages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </nav>
        )}
      </section>
    </div>
  )
}
