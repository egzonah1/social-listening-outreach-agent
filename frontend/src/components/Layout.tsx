import { useQuery } from '@tanstack/react-query'
import { Radar, ShieldCheck } from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { api } from '../lib/api'
import { AccessGate } from './AccessGate'
import { Spinner } from './ui'

export function Layout() {
  const meta = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: Infinity })

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2 font-semibold text-slate-900">
            <span className="grid size-8 place-items-center rounded-lg bg-brand-700 text-white">
              <Radar className="size-4" aria-hidden />
            </span>
            Outreach Agent
          </Link>
          <nav className="ml-4 hidden sm:block">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                isActive
                  ? 'rounded-md bg-slate-100 px-2.5 py-1.5 text-sm font-medium text-slate-900'
                  : 'rounded-md px-2.5 py-1.5 text-sm text-slate-500 hover:text-slate-900'
              }
            >
              Overview
            </NavLink>
          </nav>
          <span
            className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-800 ring-1 ring-brand-100"
            title="Every reply is written for a person to review. Nothing is posted automatically."
          >
            <ShieldCheck className="size-3.5" aria-hidden />
            Human approval required
          </span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
        {meta.isPending ? (
          <Spinner />
        ) : (
          // If /api/meta fails, show the app anyway: its own error boxes explain the problem.
          <AccessGate required={meta.data?.access_code_required ?? false}>
            <Outlet />
          </AccessGate>
        )}
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-xs text-slate-500 sm:px-6">
          <span className="inline-flex items-center gap-1">
            <ShieldCheck className="size-3.5" aria-hidden />
            Only public posts from official APIs. Nothing is ever posted automatically.
          </span>
          {meta.data && (
            <>
              <span>Collected posts are deleted after {meta.data.retention_days} days.</span>
              {meta.data.contact_email && (
                <span>
                  Data requests:{' '}
                  <a className="underline" href={`mailto:${meta.data.contact_email}`}>
                    {meta.data.contact_email}
                  </a>
                </span>
              )}
              <span className="ml-auto">v{meta.data.version}</span>
            </>
          )}
        </div>
      </footer>
    </div>
  )
}
