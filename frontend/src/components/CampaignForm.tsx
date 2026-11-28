import clsx from 'clsx'
import { X } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { KEYWORD_PRESETS, LIFE_EVENTS, PLATFORMS } from '../lib/labels'
import type { CampaignInput, LifeEvent, Platform } from '../lib/types'
import { Button, ErrorBox, Field, inputClass } from './ui'

const PICKABLE_EVENTS = Object.keys(KEYWORD_PRESETS) as LifeEvent[]
const SOURCES: { value: Platform; hint: string }[] = [
  { value: 'bluesky', hint: 'Real public posts via the official Bluesky API' },
  { value: 'mastodon', hint: 'Public hashtag posts via the official Mastodon API' },
  { value: 'sample', hint: 'Hand-written demo posts, clearly labelled' },
]
const MAX_KEYWORDS = 10

interface Props {
  onSubmit: (input: CampaignInput) => void
  onCancel: () => void
  submitting: boolean
  error: unknown
}

/** Validates in the browser for quick feedback; the server validates again. */
export function CampaignForm({ onSubmit, onCancel, submitting, error }: Props) {
  const [name, setName] = useState('')
  const [events, setEvents] = useState<LifeEvent[]>([])
  const [keywords, setKeywords] = useState<string[]>([])
  const [draftKeyword, setDraftKeyword] = useState('')
  const [sources, setSources] = useState<Platform[]>(['bluesky'])
  const [touched, setTouched] = useState(false)

  const problems = {
    name: name.trim() ? undefined : 'Give the campaign a name.',
    keywords: keywords.length ? undefined : 'Add at least one keyword.',
    sources: sources.length ? undefined : 'Pick at least one source.',
  }
  const valid = !problems.name && !problems.keywords && !problems.sources

  function addKeywords(words: string[]) {
    setKeywords((current) => {
      const next = [...current]
      for (const word of words.map((w) => w.trim()).filter((w) => w.length >= 2)) {
        if (!next.includes(word) && next.length < MAX_KEYWORDS) next.push(word)
      }
      return next
    })
  }

  function toggleEvent(event: LifeEvent) {
    const on = events.includes(event)
    setEvents(on ? events.filter((e) => e !== event) : [...events, event])
    if (!on) addKeywords(KEYWORD_PRESETS[event] ?? [])
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    setTouched(true)
    if (!valid) return
    onSubmit({ name: name.trim(), keywords, life_events: events, sources, language: 'en' })
  }

  return (
    <form onSubmit={submit} className="space-y-5" noValidate>
      <Field
        label="Campaign name"
        htmlFor="campaign-name"
        error={touched ? problems.name : undefined}
      >
        <input
          id="campaign-name"
          className={inputClass}
          value={name}
          maxLength={120}
          placeholder="e.g. New parents, November"
          onChange={(e) => setName(e.target.value)}
        />
      </Field>

      <Field label="Life events" hint="Picking one adds suggested keywords. You can remove any.">
        <div className="flex flex-wrap gap-2">
          {PICKABLE_EVENTS.map((event) => (
            <button
              key={event}
              type="button"
              aria-pressed={events.includes(event)}
              onClick={() => toggleEvent(event)}
              className={clsx(
                'rounded-full px-3 py-1 text-sm ring-1 transition-colors',
                events.includes(event)
                  ? 'bg-brand-700 text-white ring-brand-700'
                  : 'bg-white text-slate-700 ring-slate-300 hover:bg-slate-50',
              )}
            >
              {LIFE_EVENTS[event]}
            </button>
          ))}
        </div>
      </Field>

      <Field
        label={`Keywords and hashtags (${keywords.length}/${MAX_KEYWORDS})`}
        htmlFor="keyword-input"
        hint="Press Enter to add. Each keyword is searched separately."
        error={touched ? problems.keywords : undefined}
      >
        <div className="flex flex-wrap gap-1.5">
          {keywords.map((word) => (
            <span
              key={word}
              className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-sm text-slate-800"
            >
              {word}
              <button
                type="button"
                aria-label={`Remove ${word}`}
                className="text-slate-500 hover:text-slate-900"
                onClick={() => setKeywords(keywords.filter((k) => k !== word))}
              >
                <X className="size-3.5" />
              </button>
            </span>
          ))}
        </div>
        <input
          id="keyword-input"
          className={inputClass}
          value={draftKeyword}
          disabled={keywords.length >= MAX_KEYWORDS}
          placeholder={keywords.length >= MAX_KEYWORDS ? 'Keyword limit reached' : 'e.g. #newhome'}
          onChange={(e) => setDraftKeyword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ',') {
              e.preventDefault()
              addKeywords([draftKeyword])
              setDraftKeyword('')
            }
          }}
          onBlur={() => {
            if (draftKeyword.trim()) {
              addKeywords([draftKeyword])
              setDraftKeyword('')
            }
          }}
        />
      </Field>

      <Field label="Sources" error={touched ? problems.sources : undefined}>
        <div className="grid gap-2 sm:grid-cols-3">
          {SOURCES.map(({ value, hint }) => (
            <label
              key={value}
              className="flex cursor-pointer items-start gap-3 rounded-lg p-3 ring-1 ring-slate-200 hover:bg-slate-50"
            >
              <input
                type="checkbox"
                className="mt-0.5 accent-brand-700"
                checked={sources.includes(value)}
                onChange={(e) =>
                  setSources(
                    e.target.checked ? [...sources, value] : sources.filter((s) => s !== value),
                  )
                }
              />
              <span>
                <span className="block text-sm font-medium">{PLATFORMS[value]}</span>
                <span className="block text-xs text-slate-500">{hint}</span>
              </span>
            </label>
          ))}
        </div>
      </Field>

      {Boolean(error) && <ErrorBox error={error} />}

      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={submitting}>
          Create campaign
        </Button>
      </div>
    </form>
  )
}
