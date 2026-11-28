// Types mirroring the backend's API shapes (backend/app/schemas/*.py).

export type Platform = 'bluesky' | 'mastodon' | 'sample'
export type LifeEvent =
  | 'new_baby'
  | 'home_purchase'
  | 'bereavement'
  | 'new_business'
  | 'marriage'
  | 'other'
  | 'none'
export type Sensitivity = 'low' | 'medium' | 'high'
export type Recommendation = 'engage' | 'supportive_only' | 'do_not_contact'
export type PostStatus = 'new' | 'drafted' | 'approved' | 'replied' | 'dismissed'
export type DraftStatus = 'suggested' | 'approved' | 'rejected'
export type RunStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface Campaign {
  id: number
  name: string
  description: string | null
  keywords: string[]
  life_events: LifeEvent[]
  sources: Platform[]
  language: string | null
  created_at: string
  updated_at: string
}

export interface CampaignInput {
  name: string
  description?: string | null
  keywords: string[]
  life_events: LifeEvent[]
  sources: Platform[]
  language: string | null
}

export interface SourceStat {
  found: number
  new: number
  error: string | null
}

export interface SearchRun {
  id: number
  campaign_id: number
  status: RunStatus
  source_stats: Record<string, SourceStat>
  posts_found: number
  posts_new: number
  posts_analyzed: number
  posts_drafted: number
  error: string | null
  triage_error: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface Analysis {
  relevance: number
  life_event: LifeEvent
  sensitivity: Sensitivity
  recommendation: Recommendation
  reason: string
  summary: string
  model: string
}

export interface Draft {
  id: number
  tone: string
  text: string
  original_text: string
  status: DraftStatus
  warnings: string[]
  approved_at: string | null
  created_at: string
  updated_at: string
}

export interface AuditEvent {
  id: number
  entity_type: string
  entity_id: number
  action: string
  details: Record<string, unknown>
  created_at: string
}

export interface Post {
  id: number
  campaign_id: number
  platform: Platform
  url: string
  author_handle: string
  author_display_name: string | null
  text: string
  language: string | null
  posted_at: string
  like_count: number
  reply_count: number
  repost_count: number
  matched_keyword: string | null
  is_sample: boolean
  status: PostStatus
  analysis: Analysis | null
}

export interface PostDetail extends Post {
  drafts: Draft[]
  audit: AuditEvent[]
}

export interface PostPage {
  items: Post[]
  total: number
}

export interface CampaignStats {
  total_posts: number
  by_status: Record<string, number>
  by_life_event: Record<string, number>
  by_recommendation: Record<string, number>
}

export interface Meta {
  app_name: string
  version: string
  contact_email: string | null
  retention_days: number
  access_code_required: boolean
}

export interface PostFilters {
  life_event?: LifeEvent | ''
  status?: PostStatus | ''
  include_do_not_contact?: boolean
  sort?: 'relevance' | 'newest'
}

export interface CampaignSummary {
  campaign: Campaign
  posts: number
  to_review: number
  approved: number
  replied: number
  last_run: SearchRun | null
}

export interface Overview {
  totals: { campaigns: number; posts: number; to_review: number; approved: number; replied: number }
  campaigns: CampaignSummary[]
}
