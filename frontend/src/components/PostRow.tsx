import clsx from 'clsx'
import { ChevronRight, FlaskConical, Wrench } from 'lucide-react'
import { Link } from 'react-router-dom'
import { isRulesModel, timeAgo } from '../lib/format'
import { LIFE_EVENTS, PLATFORMS, POST_STATUS, RECOMMENDATIONS, SENSITIVITY } from '../lib/labels'
import type { Post } from '../lib/types'
import { Avatar, Badge } from './ui'

/** Green for a strong match, amber for a maybe, grey for a weak one. */
function relevanceClass(score: number): string {
  if (score >= 70) return 'bg-emerald-50 text-emerald-700 ring-emerald-200'
  if (score >= 40) return 'bg-amber-50 text-amber-800 ring-amber-200'
  return 'bg-slate-50 text-slate-600 ring-slate-200'
}

/** One post in the review inbox: who wrote it, what it's about, and what to do. */
export function PostRow({ post }: { post: Post }) {
  const a = post.analysis
  const status = POST_STATUS[post.status]
  const name = post.author_display_name || post.author_handle
  return (
    <Link
      to={`/posts/${post.id}`}
      className="group flex gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 transition hover:shadow-md hover:ring-brand-600/60"
    >
      <Avatar name={name} />
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex items-start justify-between gap-3">
          <p className="min-w-0 truncate text-sm">
            <span className="font-medium text-slate-900">{name}</span>{' '}
            <span className="text-slate-500">
              @{post.author_handle} · {timeAgo(post.posted_at)}
            </span>
          </p>
          {a && (
            <span
              className={clsx(
                'shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ring-1',
                relevanceClass(a.relevance),
              )}
              title="Relevance score (0-100)"
            >
              {a.relevance} match
            </span>
          )}
        </div>

        {a?.summary && <p className="text-sm font-medium text-slate-900">{a.summary}</p>}
        <p className="line-clamp-2 text-sm text-slate-600">{post.text}</p>

        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
          {a ? (
            <>
              <Badge tone={RECOMMENDATIONS[a.recommendation].tone}>
                {RECOMMENDATIONS[a.recommendation].label}
              </Badge>
              <Badge tone="brand">{LIFE_EVENTS[a.life_event]}</Badge>
              {a.sensitivity !== 'low' && (
                <Badge tone={SENSITIVITY[a.sensitivity].tone}>
                  {SENSITIVITY[a.sensitivity].label}
                </Badge>
              )}
            </>
          ) : (
            <Badge>Waiting for sorting</Badge>
          )}
          {post.status !== 'new' && <Badge tone={status.tone}>{status.label}</Badge>}
          <span className="ml-1 inline-flex flex-wrap items-center gap-x-2 text-xs text-slate-400">
            {post.is_sample ? (
              <span className="inline-flex items-center gap-1" title="Hand-written demo post, not a real person">
                <FlaskConical className="size-3" aria-hidden />
                Sample
              </span>
            ) : (
              <span>{PLATFORMS[post.platform]}</span>
            )}
            {a && isRulesModel(a.model) && (
              <span
                className="inline-flex items-center gap-1 text-amber-700"
                title="The AI was unavailable, so keyword rules decided this."
              >
                <Wrench className="size-3" aria-hidden />
                Backup rules
              </span>
            )}
            {post.matched_keyword && <span>matched "{post.matched_keyword}"</span>}
          </span>
        </div>
      </div>
      <ChevronRight className="size-5 shrink-0 self-center text-slate-300 group-hover:text-brand-700" />
    </Link>
  )
}
