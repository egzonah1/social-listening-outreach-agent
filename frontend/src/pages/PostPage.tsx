import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Ban,
  CheckCheck,
  ExternalLink,
  FlaskConical,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { DraftCard } from '../components/DraftCard'
import { ProgressSteps } from '../components/ProgressSteps'
import { PostPageSkeleton } from '../components/Skeletons'
import { Avatar, Badge, Button, Card, ErrorBox, Spinner, inputClass } from '../components/ui'
import { api } from '../lib/api'
import { dateTime, isRulesModel, timeAgo } from '../lib/format'
import {
  AUDIT_ACTIONS,
  CHAR_LIMITS,
  LIFE_EVENTS,
  PLATFORMS,
  POST_STATUS,
  RECOMMENDATIONS,
  SENSITIVITY,
} from '../lib/labels'
import type { PostDetail } from '../lib/types'

export function PostPage() {
  const postId = Number(useParams().postId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [instruction, setInstruction] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const key = ['post', postId]

  const post = useQuery({ queryKey: key, queryFn: () => api.post(postId) })

  const setDetail = (detail: PostDetail) => {
    queryClient.setQueryData(key, detail)
    void queryClient.invalidateQueries({ queryKey: ['posts', detail.campaign_id] })
    void queryClient.invalidateQueries({ queryKey: ['stats', detail.campaign_id] })
  }
  const refresh = () => queryClient.invalidateQueries({ queryKey: key })

  const generate = useMutation({
    mutationFn: () => api.generateDrafts(postId, instruction.trim()),
    onSuccess: (detail) => {
      setDetail(detail)
      setInstruction('')
    },
  })
  const saveDraft = useMutation({
    mutationFn: ({ id, text }: { id: number; text: string }) => api.updateDraft(id, text),
    onSuccess: refresh,
  })
  const approve = useMutation({ mutationFn: api.approveDraft, onSuccess: refresh })
  const reject = useMutation({ mutationFn: api.rejectDraft, onSuccess: refresh })
  const replied = useMutation({ mutationFn: () => api.markReplied(postId), onSuccess: setDetail })
  const dismiss = useMutation({ mutationFn: () => api.dismiss(postId), onSuccess: setDetail })
  const remove = useMutation({
    mutationFn: () => api.deletePost(postId),
    onSuccess: () => {
      const campaignId = post.data?.campaign_id
      void queryClient.invalidateQueries({ queryKey: ['posts', campaignId] })
      navigate(campaignId ? `/campaigns/${campaignId}` : '/')
    },
  })

  if (post.isPending) return <PostPageSkeleton />
  if (post.isError) return <ErrorBox error={post.error} onRetry={() => void post.refetch()} />

  const p = post.data
  const a = p.analysis
  const limit = CHAR_LIMITS[p.platform]
  const drafts = p.drafts
  const hasApproved = drafts.some((d) => d.status === 'approved')
  const draftBusy = saveDraft.isPending || approve.isPending || reject.isPending
  const actionError =
    generate.error ?? saveDraft.error ?? approve.error ?? reject.error ?? replied.error ?? dismiss.error ?? remove.error
  const closed = p.status === 'replied' || p.status === 'dismissed'

  return (
    <div className="space-y-6">
      <Link
        to={`/campaigns/${p.campaign_id}`}
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="size-4" /> Back to inbox
      </Link>

      <ProgressSteps post={p} />

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Left: the post and the AI's reading of it */}
        <div className="space-y-4 lg:col-span-2">
          <Card className="p-4">
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              {!p.is_sample && <Badge tone="blue">{PLATFORMS[p.platform]}</Badge>}
              <Badge tone={POST_STATUS[p.status].tone}>{POST_STATUS[p.status].label}</Badge>
              {p.is_sample && (
                <Badge tone="violet" title="Hand-written demo post, not a real person">
                  <FlaskConical className="size-3" aria-hidden /> Sample data
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-3">
              <Avatar name={p.author_display_name || p.author_handle} size="lg" />
              <p className="min-w-0 text-sm">
                <span className="block truncate font-semibold">{p.author_display_name ?? p.author_handle}</span>
                <span className="block truncate text-slate-500">@{p.author_handle}</span>
              </p>
            </div>
            <p className="mt-2 whitespace-pre-wrap text-[15px] leading-relaxed">{p.text}</p>
            <p className="mt-3 text-xs text-slate-500" title={dateTime(p.posted_at)}>
              Posted {timeAgo(p.posted_at)} · {p.like_count} likes · {p.reply_count} replies
              {p.matched_keyword && ` · matched "${p.matched_keyword}"`}
            </p>
            {!p.is_sample && (
              <a
                href={p.url}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline"
              >
                Open the original post <ExternalLink className="size-3.5" />
              </a>
            )}
          </Card>

          <Card className="p-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Sparkles className="size-4 text-brand-700" aria-hidden /> AI assessment
            </h2>
            {a ? (
              <div className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-1.5">
                  <Badge tone={RECOMMENDATIONS[a.recommendation].tone}>
                    {RECOMMENDATIONS[a.recommendation].label}
                  </Badge>
                  <Badge tone="brand">{LIFE_EVENTS[a.life_event]}</Badge>
                  <Badge tone={SENSITIVITY[a.sensitivity].tone}>{SENSITIVITY[a.sensitivity].label}</Badge>
                </div>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
                  <dt className="text-slate-500">Relevance</dt>
                  <dd>
                    <Meter value={a.relevance} />
                  </dd>
                  <dt className="text-slate-500">Summary</dt>
                  <dd>{a.summary}</dd>
                  <dt className="text-slate-500">Why</dt>
                  <dd>{a.reason}</dd>
                  <dt className="text-slate-500">Decided by</dt>
                  <dd>
                    {isRulesModel(a.model) ? (
                      <Badge tone="amber">Backup keyword rules (AI unavailable)</Badge>
                    ) : (
                      <span className="text-slate-600">{a.model}</span>
                    )}
                  </dd>
                </dl>
                <p className="text-xs text-slate-500">{RECOMMENDATIONS[a.recommendation].hint}</p>
              </div>
            ) : (
              <p className="text-sm text-slate-500">Not sorted yet. It's done automatically after each search.</p>
            )}
          </Card>

          <AuditTrail post={p} />
        </div>

        {/* Right: drafts and actions */}
        <div className="space-y-4 lg:col-span-3">
          {a?.recommendation === 'do_not_contact' && (
            <Notice tone="red" icon={<Ban className="size-4" />}>
              The AI recommends <strong>not contacting</strong> this person. Drafting is still
              possible, but think twice.
            </Notice>
          )}
          {a?.recommendation === 'supportive_only' && (
            <Notice tone="amber" icon={<ShieldAlert className="size-4" />}>
              Sensitive post: replies should offer kindness only, with no mention of insurance.
            </Notice>
          )}

          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Reply drafts</h2>
            <span className="text-xs text-slate-500">
              Nothing is sent from this app. You post the approved reply yourself.
            </span>
          </div>

          {actionError && <ErrorBox error={actionError} />}

          {drafts.length === 0 && !generate.isPending && (
            <Card className="p-6 text-center">
              <p className="text-sm text-slate-600">No drafts for this post yet.</p>
              <Button className="mt-3" icon={<Sparkles className="size-4" />} onClick={() => generate.mutate()} disabled={closed}>
                Write reply drafts
              </Button>
            </Card>
          )}
          {generate.isPending && <Spinner label="Writing reply drafts… usually a few seconds" />}

          {drafts.map((draft) => (
            <DraftCard
              key={`${draft.id}-${draft.updated_at}`}
              draft={draft}
              limit={limit}
              busy={draftBusy}
              onSave={(text) => saveDraft.mutateAsync({ id: draft.id, text })}
              onApprove={() => approve.mutate(draft.id)}
              onReject={() => reject.mutate(draft.id)}
            />
          ))}

          {drafts.length > 0 && !closed && (
            <Card className="p-4">
              <label htmlFor="instruction" className="text-sm font-medium">
                Not quite right? Ask for new drafts
              </label>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                <input
                  id="instruction"
                  className={inputClass}
                  maxLength={300}
                  placeholder='e.g. "shorter, no mention of insurance"'
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                />
                <Button
                  variant="secondary"
                  icon={<RefreshCw className="size-4" />}
                  loading={generate.isPending}
                  onClick={() => generate.mutate()}
                >
                  Regenerate
                </Button>
              </div>
              <p className="mt-1 text-xs text-slate-500">Approved drafts are kept.</p>
            </Card>
          )}

          <Card className="flex flex-wrap items-center gap-2 p-4">
            <Button
              icon={<CheckCheck className="size-4" />}
              disabled={!hasApproved || closed}
              loading={replied.isPending}
              onClick={() => replied.mutate()}
              title={hasApproved ? undefined : 'Approve a draft first'}
            >
              {p.is_sample ? 'Mark as replied' : `I replied on ${PLATFORMS[p.platform]}`}
            </Button>
            <Button variant="secondary" disabled={closed} loading={dismiss.isPending} onClick={() => dismiss.mutate()}>
              Dismiss
            </Button>
            <div className="ml-auto">
              {confirmDelete ? (
                <span className="flex items-center gap-2 text-sm">
                  Delete all data for this post?
                  <Button size="sm" variant="danger" loading={remove.isPending} onClick={() => remove.mutate()}>
                    Yes, delete
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(false)}>
                    Cancel
                  </Button>
                </span>
              ) : (
                <Button variant="danger" icon={<Trash2 className="size-4" />} onClick={() => setConfirmDelete(true)}>
                  Delete data
                </Button>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

function Meter({ value }: { value: number }) {
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100" aria-hidden>
        <span className="block h-full rounded-full bg-brand-600" style={{ width: `${value}%` }} />
      </span>
      <span className="tabular-nums">{value}/100</span>
    </span>
  )
}

function Notice({ tone, icon, children }: { tone: 'red' | 'amber'; icon: ReactNode; children: ReactNode }) {
  const styles = tone === 'red' ? 'bg-red-50 text-red-800 ring-red-200' : 'bg-amber-50 text-amber-900 ring-amber-200'
  return (
    <div className={`flex items-start gap-2 rounded-lg p-3 text-sm ring-1 ${styles}`}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <p>{children}</p>
    </div>
  )
}

function AuditTrail({ post }: { post: PostDetail }) {
  if (post.audit.length === 0) return null
  return (
    <Card className="p-4">
      <h2 className="mb-3 text-sm font-semibold">History</h2>
      <ol className="space-y-2 border-l border-slate-200 pl-4">
        {post.audit.map((event) => (
          <li key={event.id} className="relative text-sm">
            <span className="absolute -left-[21px] top-1.5 size-2 rounded-full bg-slate-300" aria-hidden />
            <p>{AUDIT_ACTIONS[event.action] ?? event.action}</p>
            <p className="text-xs text-slate-500">{dateTime(event.created_at)}</p>
          </li>
        ))}
      </ol>
    </Card>
  )
}
