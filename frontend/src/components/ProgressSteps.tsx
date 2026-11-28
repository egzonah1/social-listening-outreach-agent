import clsx from 'clsx'
import { Ban, Check } from 'lucide-react'
import { stepsDone } from '../lib/progress'
import type { PostDetail } from '../lib/types'

const STEPS = ['Found', 'Sorted', 'Drafted', 'Approved', 'Replied'] as const

/** Where a post is in the process, from "found" to "you replied". A person does the last two steps. */
export function ProgressSteps({ post }: { post: PostDetail }) {
  const done = stepsDone(post)
  const stopped =
    post.status === 'dismissed'
      ? 'Dismissed'
      : post.analysis?.recommendation === 'do_not_contact'
        ? 'Do not contact'
        : null
  const steps = stopped ? [...STEPS.slice(0, 2), stopped] : STEPS

  return (
    <ol className="flex items-center gap-1 overflow-x-auto rounded-xl bg-white px-4 py-3 shadow-sm ring-1 ring-slate-200" aria-label="Progress">
      {steps.map((label, i) => {
        const isStop = stopped !== null && i === steps.length - 1
        const complete = !isStop && i < done
        const current = !isStop && i === done
        return (
          <li key={label} className="flex shrink-0 items-center gap-1">
            {i > 0 && (
              <span
                className={clsx('h-px w-6 sm:w-10', complete || isStop ? 'bg-brand-600' : 'bg-slate-200')}
                aria-hidden
              />
            )}
            <span
              className={clsx(
                'grid size-6 place-items-center rounded-full text-xs font-semibold',
                isStop && 'bg-red-100 text-red-700',
                complete && 'bg-brand-700 text-white',
                current && 'bg-brand-50 text-brand-700 ring-2 ring-brand-600',
                !isStop && !complete && !current && 'bg-slate-100 text-slate-400',
              )}
              aria-hidden
            >
              {isStop ? <Ban className="size-3.5" /> : complete ? <Check className="size-3.5" /> : i + 1}
            </span>
            <span
              className={clsx(
                'text-xs font-medium',
                isStop ? 'text-red-700' : complete || current ? 'text-slate-900' : 'text-slate-400',
              )}
              aria-current={current ? 'step' : undefined}
            >
              {label}
            </span>
          </li>
        )
      })}
      {!stopped && done < 5 && (
        <li className="ml-auto hidden shrink-0 pl-4 text-xs text-slate-500 md:block">
          {done >= 3 ? 'Next: you approve a reply and post it yourself' : 'Next: reply drafts'}
        </li>
      )}
    </ol>
  )
}
