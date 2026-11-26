import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CampaignForm } from '../components/CampaignForm'
import { Badge, Button, Card, EmptyState, ErrorBox, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { timeAgo } from '../lib/format'
import { LIFE_EVENTS, PLATFORMS } from '../lib/labels'

export function CampaignsPage() {
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const campaigns = useQuery({ queryKey: ['campaigns'], queryFn: api.campaigns })
  const create = useMutation({
    mutationFn: api.createCampaign,
    onSuccess: (campaign) => {
      void queryClient.invalidateQueries({ queryKey: ['campaigns'] })
      navigate(`/campaigns/${campaign.id}`)
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Campaigns</h1>
          <p className="mt-1 text-sm text-slate-500">
            A campaign is a set of keywords for one kind of life event. Run it to find public
            posts, then review the AI's suggestions.
          </p>
        </div>
        {!creating && (
          <Button icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
            New campaign
          </Button>
        )}
      </div>

      {creating && (
        <Card className="p-5">
          <h2 className="mb-4 text-base font-semibold">New campaign</h2>
          <CampaignForm
            submitting={create.isPending}
            error={create.error}
            onCancel={() => setCreating(false)}
            onSubmit={(input) => create.mutate(input)}
          />
        </Card>
      )}

      {campaigns.isPending && <Spinner label="Loading campaigns…" />}
      {campaigns.isError && (
        <ErrorBox error={campaigns.error} onRetry={() => void campaigns.refetch()} />
      )}
      {campaigns.data?.length === 0 && !creating && (
        <EmptyState
          title="No campaigns yet"
          action={<Button onClick={() => setCreating(true)}>Create your first campaign</Button>}
        >
          Start with a life event such as "New baby". We'll suggest keywords for you.
        </EmptyState>
      )}

      {campaigns.data && campaigns.data.length > 0 && (
        <ul className="grid gap-3">
          {campaigns.data.map((campaign) => (
            <li key={campaign.id}>
              <Link
                to={`/campaigns/${campaign.id}`}
                className="group flex items-center gap-4 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 transition hover:ring-brand-600"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-medium text-slate-900">{campaign.name}</h2>
                    {campaign.life_events.map((event) => (
                      <Badge key={event} tone="brand">
                        {LIFE_EVENTS[event]}
                      </Badge>
                    ))}
                  </div>
                  <p className="mt-1 truncate text-sm text-slate-500">
                    {campaign.keywords.join(' · ')}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {campaign.sources.map((s) => PLATFORMS[s]).join(', ')} · created{' '}
                    {timeAgo(campaign.created_at)}
                  </p>
                </div>
                <ChevronRight className="size-5 text-slate-400 group-hover:text-brand-700" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
