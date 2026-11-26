import { useQueryClient } from '@tanstack/react-query'
import { KeyRound } from 'lucide-react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { ACCESS_DENIED_EVENT, clearAccessCode, getAccessCode, setAccessCode } from '../lib/access'
import { ApiError, api } from '../lib/api'
import { Button, Card, Field, inputClass } from './ui'

/** Shows the app only after a valid access code, when the server asks for one. */
export function AccessGate({ required, children }: { required: boolean; children: ReactNode }) {
  const [unlocked, setUnlocked] = useState(() => getAccessCode() !== null)
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const queryClient = useQueryClient()

  useEffect(() => {
    const lock = () => setUnlocked(false)
    window.addEventListener(ACCESS_DENIED_EVENT, lock)
    return () => window.removeEventListener(ACCESS_DENIED_EVENT, lock)
  }, [])

  if (!required || unlocked) return <>{children}</>

  async function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = code.trim()
    if (!trimmed) return
    setChecking(true)
    setError(null)
    setAccessCode(trimmed)
    try {
      await api.campaigns() // any protected call tells us if the code works
      await queryClient.invalidateQueries()
      setUnlocked(true)
      setCode('')
    } catch (err) {
      clearAccessCode()
      setError(
        err instanceof ApiError && err.status === 401
          ? 'That code is not right. Check the email with the link.'
          : err instanceof Error
            ? err.message
            : 'Something went wrong.',
      )
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <Card className="p-6">
        <div className="mb-4 flex items-center gap-2">
          <KeyRound className="size-5 text-brand-700" aria-hidden />
          <h1 className="text-lg font-semibold text-slate-900">Enter access code</h1>
        </div>
        <p className="mb-4 text-sm text-slate-600">
          This demo is private. Use the access code you received with the link.
        </p>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Access code" htmlFor="access-code" error={error ?? undefined}>
            <input
              id="access-code"
              type="password"
              autoComplete="off"
              className={inputClass}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoFocus
            />
          </Field>
          <Button type="submit" loading={checking} disabled={!code.trim()} className="w-full">
            Continue
          </Button>
        </form>
      </Card>
    </div>
  )
}
