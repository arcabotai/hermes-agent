import { expect, it } from 'vitest'

import { TRANSLATIONS } from '@/i18n'

import { parseErrorSurface } from './error-surface'
import { errorCardText } from './error-surface-copy'

// A rejected credential is the one error card a user must act on (#142455): its
// heading, body and "Update API key" button have to read in the UI language,
// not fall back to English next to an already-translated Retry row.
const LOCALES = ['zh', 'zh-hant', 'ja', 'ru', 'ar'] as const

it.each(LOCALES)('words a rejected API key in %s and keeps the provider name', locale => {
  const surface = parseErrorSurface({
    layer: 'auth',
    code: 'auth',
    auth_kind: 'api_key',
    provider: 'fixture-provider',
    provider_label: 'Provider Ω',
    retryable: false
  })

  const copy = errorCardText(TRANSLATIONS[locale].assistant.thread, surface)
  const english = errorCardText(TRANSLATIONS.en.assistant.thread, surface)

  expect(copy.title).not.toBe(english.title)
  expect(copy.body).not.toBe(english.body)
  expect(copy.title).toContain('Provider Ω')
  expect(copy.body).toContain('Provider Ω')
})

it.each(LOCALES)('words an expired sign-in card in %s', locale => {
  const surface = parseErrorSurface({
    layer: 'auth',
    code: 'auth',
    auth_kind: 'oauth',
    provider: 'fixture-provider',
    provider_label: 'Provider Ω',
    retryable: false
  })

  const copy = errorCardText(TRANSLATIONS[locale].assistant.thread, surface)
  const english = errorCardText(TRANSLATIONS.en.assistant.thread, surface)

  expect(copy.title).not.toBe(english.title)
  expect(copy.body).not.toBe(english.body)
  expect(copy.title).toContain('Provider Ω')
})

it.each(LOCALES)('labels the error card key button and details toggle in %s', locale => {
  const thread = TRANSLATIONS[locale].assistant.thread

  expect(thread.errorUpdateApiKey).not.toBe(TRANSLATIONS.en.assistant.thread.errorUpdateApiKey)
  expect(thread.errorDetails).not.toBe(TRANSLATIONS.en.assistant.thread.errorDetails)
})
