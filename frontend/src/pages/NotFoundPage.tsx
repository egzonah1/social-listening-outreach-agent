import { Link } from 'react-router-dom'
import { EmptyState } from '../components/ui'

export function NotFoundPage() {
  return (
    <EmptyState
      title="Page not found"
      action={
        <Link className="text-sm font-medium text-brand-700 underline" to="/">
          Back to campaigns
        </Link>
      }
    >
      This page doesn't exist, or the data behind it was deleted.
    </EmptyState>
  )
}
