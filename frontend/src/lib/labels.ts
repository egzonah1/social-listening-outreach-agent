// Human-readable labels and colours for the backend's fixed vocabularies,
// plus keyword presets per life event (so nobody starts from a blank form).

import type { LifeEvent, Platform, PostStatus, Recommendation, Sensitivity } from './types'

export const LIFE_EVENTS: Record<LifeEvent, string> = {
  new_baby: 'New baby',
  home_purchase: 'New home',
  bereavement: 'Bereavement',
  new_business: 'New business',
  marriage: 'Marriage',
  other: 'Other event',
  none: 'No life event',
}

/**
 * Keyword ideas per life event. Hashtags work well on Bluesky.
 * Mastodon turns every keyword into a hashtag ("new baby" -> #newbaby).
 */
export const KEYWORD_PRESETS: Partial<Record<LifeEvent, string[]>> = {
  new_baby: ['new baby', 'baby arrived', '#newborn', 'first baby'],
  home_purchase: ['bought a house', 'first home', '#newhome', 'got the keys'],
  bereavement: ['passed away', '#grief', 'lost my dad', 'lost my mom'],
  new_business: ['started my own business', 'small business owner', 'launched my business'],
  marriage: ['got married', 'just married', '#engaged', 'our wedding'],
}

export const PLATFORMS: Record<Platform, string> = {
  bluesky: 'Bluesky',
  mastodon: 'Mastodon',
  sample: 'Sample data',
}

/** Same limits as backend/app/ai/guardrails.py. */
export const CHAR_LIMITS: Record<Platform, number> = { bluesky: 300, mastodon: 500, sample: 300 }

export const RECOMMENDATIONS: Record<Recommendation, { label: string; tone: Tone; hint: string }> = {
  engage: {
    label: 'Engage',
    tone: 'green',
    hint: 'A friendly reply could be welcome.',
  },
  supportive_only: {
    label: 'Supportive only',
    tone: 'amber',
    hint: 'Kindness only: no mention of insurance.',
  },
  do_not_contact: {
    label: 'Do not contact',
    tone: 'red',
    hint: 'Leave this person alone.',
  },
}

export const SENSITIVITY: Record<Sensitivity, { label: string; tone: Tone }> = {
  low: { label: 'Low sensitivity', tone: 'slate' },
  medium: { label: 'Medium sensitivity', tone: 'amber' },
  high: { label: 'High sensitivity', tone: 'red' },
}

export const POST_STATUS: Record<PostStatus, { label: string; tone: Tone }> = {
  new: { label: 'New', tone: 'blue' },
  drafted: { label: 'Drafted', tone: 'violet' },
  approved: { label: 'Approved', tone: 'green' },
  replied: { label: 'Replied', tone: 'slate' },
  dismissed: { label: 'Dismissed', tone: 'slate' },
}

export type Tone = 'slate' | 'blue' | 'green' | 'amber' | 'red' | 'violet' | 'brand'

/** Audit log actions in plain words. */
export const AUDIT_ACTIONS: Record<string, string> = {
  'drafts.generated': 'Reply drafts written',
  'draft.edited': 'Draft edited',
  'draft.approved': 'Draft approved',
  'draft.rejected': 'Draft rejected',
  'post.replied_manually': 'Marked as replied (sent by hand on the platform)',
  'post.dismissed': 'Post dismissed',
  'post.data_deleted': 'Post data deleted',
  'author.blocked': 'Author added to the do-not-contact list',
}
