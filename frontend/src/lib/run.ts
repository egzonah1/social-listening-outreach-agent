import type { SearchRun } from './types'

/** A run is active until sorting and background drafting have finished. */
export const isActive = (run?: SearchRun) => run?.status === 'queued' || run?.status === 'running'
