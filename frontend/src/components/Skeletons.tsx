// Grey placeholder shapes shown while data loads. They have the same size as
// the real content, so the page doesn't jump when the data arrives.

import clsx from 'clsx'
import type { ReactNode } from 'react'

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={clsx('animate-pulse rounded-md bg-slate-200/70', className)} />
}

function Loading({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="status" aria-label={label}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  )
}

export function OverviewSkeleton() {
  return (
    <Loading label="Loading overview…">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-3 h-7 w-12" />
          </div>
        ))}
      </div>
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {[0, 1].map((i) => (
          <div key={i} className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="mt-2 h-3 w-56" />
            <div className="mt-4 grid grid-cols-3 gap-2">
              <Skeleton className="h-12" />
              <Skeleton className="h-12" />
              <Skeleton className="h-12" />
            </div>
          </div>
        ))}
      </div>
    </Loading>
  )
}

export function PostListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <Loading label="Loading posts…">
      <ul className="grid gap-3">
        {Array.from({ length: rows }, (_, i) => (
          <li key={i} className="flex gap-3 rounded-xl bg-white p-4 ring-1 ring-slate-200">
            <Skeleton className="size-9 shrink-0 rounded-full" />
            <div className="flex-1">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="mt-2 h-3 w-full" />
              <Skeleton className="mt-1.5 h-3 w-4/5" />
            </div>
          </li>
        ))}
      </ul>
    </Loading>
  )
}

export function PostPageSkeleton() {
  return (
    <Loading label="Loading post…">
      <Skeleton className="h-4 w-28" />
      <Skeleton className="mt-6 h-12 w-full rounded-xl" />
      <div className="mt-6 grid gap-6 lg:grid-cols-[2fr_3fr]">
        <div className="grid gap-4">
          <Skeleton className="h-56 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
        <div className="grid gap-4">
          <Skeleton className="h-36 rounded-xl" />
          <Skeleton className="h-36 rounded-xl" />
          <Skeleton className="h-36 rounded-xl" />
        </div>
      </div>
    </Loading>
  )
}
