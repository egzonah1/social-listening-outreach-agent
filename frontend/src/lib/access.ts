// The access code for the public demo, kept in this browser so it is asked once.
// The server decides whether a code is needed (GET /api/meta) and checks it on
// every call; this file only remembers it and announces when it was refused.

const KEY = 'outreach.accessCode'
export const ACCESS_DENIED_EVENT = 'outreach:access-denied'

export function getAccessCode(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function setAccessCode(code: string): void {
  localStorage.setItem(KEY, code)
}

export function clearAccessCode(): void {
  localStorage.removeItem(KEY)
}

export function announceAccessDenied(): void {
  window.dispatchEvent(new Event(ACCESS_DENIED_EVENT))
}
