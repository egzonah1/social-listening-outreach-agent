import type { PostDetail } from './types'

/** How many steps are done for this post (0-5). */
export function stepsDone(post: PostDetail): number {
  if (post.status === 'replied') return 5
  if (post.drafts.some((d) => d.status === 'approved')) return 4
  if (post.drafts.length > 0) return 3
  if (post.analysis) return 2
  return 1
}
