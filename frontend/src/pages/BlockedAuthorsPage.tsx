import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, UserX } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { PostListSkeleton } from '../components/Skeletons'
import { Button, Card, EmptyState, ErrorBox, Field, inputClass, selectClass } from '../components/ui'
import { api } from '../lib/api'
import { dateTime } from '../lib/format'
import { PLATFORMS } from '../lib/labels'
import type { Platform } from '../lib/types'

const BLOCKABLE: Platform[] = ['bluesky', 'mastodon', 'sample']

/**
 * People who must never be contacted. Blocking deletes their collected posts
 * everywhere, and later searches skip them before anything is stored.
 */
export function BlockedAuthorsPage() {
  const queryClient = useQueryClient()
  const list = useQuery({ queryKey: ['blocked'], queryFn: api.blockedAuthors })
  const [platform, setPlatform] = useState<Platform>('bluesky')
  const [handle, setHandle] = useState('')
  const [reason, setReason] = useState('')
  const [notice, setNotice] = useState<string | null>(null)

  const refreshAll = () => {
    void queryClient.invalidateQueries({ queryKey: ['blocked'] })
    // Their posts may have disappeared from inboxes and totals.
    void queryClient.invalidateQueries({ queryKey: ['posts'] })
    void queryClient.invalidateQueries({ queryKey: ['overview'] })
  }
  const add = useMutation({
    mutationFn: () => api.blockAuthor(platform, handle.trim(), reason.trim()),
    onSuccess: (result) => {
      setHandle('')
      setReason('')
      setNotice(
        `@${result.blocked.author_handle} will not be contacted. ${result.posts_deleted} collected post(s) deleted.`,
      )
      refreshAll()
    },
  })
  const remove = useMutation({
    mutationFn: api.unblockAuthor,
    onSuccess: refreshAll,
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (handle.trim()) add.mutate()
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Do not contact</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          People on this list are never shown again, in any campaign. Adding someone deletes the posts of theirs the app
          has collected. Only the handle is kept, never what they wrote.
        </p>
      </div>

      <Card className="p-4">
        <form onSubmit={submit} className="grid items-end gap-3 sm:grid-cols-[auto_1fr_1fr_auto]">
          <Field label="Platform" htmlFor="block-platform">
            <select
              id="block-platform"
              className={selectClass}
              value={platform}
              onChange={(e) => setPlatform(e.target.value as Platform)}
            >
              {BLOCKABLE.map((p) => (
                <option key={p} value={p}>
                  {PLATFORMS[p]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Handle" htmlFor="block-handle">
            <input
              id="block-handle"
              className={inputClass}
              placeholder="e.g. maya.bsky.social"
              value={handle}
              onChange={(e) => setHandle(e.target.value)}
            />
          </Field>
          <Field label="Reason (optional)" htmlFor="block-reason">
            <input
              id="block-reason"
              className={inputClass}
              placeholder="e.g. asked by email"
              maxLength={200}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
          <Button
            type="submit"
            variant="danger"
            icon={<Ban className="size-4" />}
            loading={add.isPending}
            disabled={!handle.trim()}
          >
            Add to list
          </Button>
        </form>
        {add.isError && (
          <div className="mt-3">
            <ErrorBox error={add.error} />
          </div>
        )}
        {notice && (
          <p role="status" className="mt-3 text-sm text-brand-800">
            {notice}
          </p>
        )}
      </Card>

      {list.isPending && <PostListSkeleton rows={2} />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {list.data?.length === 0 && (
        <EmptyState title="Nobody on the list">
          Add someone here, or use "Never contact this author" on a post.
        </EmptyState>
      )}
      {list.data && list.data.length > 0 && (
        <Card className="divide-y divide-slate-100">
          {list.data.map((entry) => (
            <div key={entry.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <UserX className="size-4 text-slate-400" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-900">@{entry.author_handle}</p>
                <p className="text-xs text-slate-500">
                  {PLATFORMS[entry.platform]} · added {dateTime(entry.created_at)}
                  {entry.reason && ` · ${entry.reason}`}
                </p>
              </div>
              <Button
                size="sm"
                variant="ghost"
                loading={remove.isPending && remove.variables === entry.id}
                onClick={() => remove.mutate(entry.id)}
              >
                Remove
              </Button>
            </div>
          ))}
        </Card>
      )}
    </div>
  )
}
