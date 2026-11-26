import { ChevronRight, FlaskConical } from 'lucide-react'
import { Link } from 'react-router-dom'
import { isRulesModel, timeAgo } from '../lib/format'
import { LIFE_EVENTS, PLATFORMS, POST_STATUS, RECOMMENDATIONS, SENSITIVITY } from '../lib/labels'
import type { Post } from '../lib/types'
import { Badge } from './ui'

/** One post in the review inbox: what the AI thinks, at a glance. */
export function PostRow({ post }: { post: Post }) {
  const a = post.analysis
  const status = POST_STATUS[post.status]
  return (
    <Link
      to={`/posts/${post.id}`}
      className="group flex gap-4 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 transition hover:ring-brand-600"
    >
      <div
        className="grid size-12 shrink-0 place-items-center rounded-lg bg-slate-50 text-lg font-semibold text-slate-800 ring-1 ring-slate-200"
        title="Relevance score (0-100)"
      >
        {a ? a.relevance : '…'}
      </div>
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
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
              {isRulesModel(a.model) && (
                <Badge tone="amber" title="The AI was unavailable, so keyword rules decided this.">
                  Backup rules
                </Badge>
              )}
            </>
          ) : (
            <Badge>Waiting for AI sorting</Badge>
          )}
          <Badge tone={status.tone}>{status.label}</Badge>
          {post.is_sample && (
            <Badge tone="violet" title="Hand-written demo post, not a real person">
              <FlaskConical className="size-3" aria-hidden /> Sample
            </Badge>
          )}
        </div>
        {a?.summary && <p className="text-sm font-medium text-slate-900">{a.summary}</p>}
        <p className="line-clamp-2 text-sm text-slate-600">{post.text}</p>
        <p className="text-xs text-slate-400">
          {PLATFORMS[post.platform]} · @{post.author_handle} · {timeAgo(post.posted_at)}
          {post.matched_keyword && ` · matched "${post.matched_keyword}"`}
        </p>
      </div>
      <ChevronRight className="size-5 shrink-0 self-center text-slate-400 group-hover:text-brand-700" />
    </Link>
  )
}
