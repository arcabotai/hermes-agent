// The rejected-API-key card in a non-English UI (#142455): the whole card, not
// just its Retry row, renders in the selected language.
import { AssistantRuntimeProvider, type ThreadMessage, useExternalStoreRuntime } from '@assistant-ui/react'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, it } from 'vitest'

import { I18nProvider } from '@/i18n/context'
import { en } from '@/i18n/en'
import { zh } from '@/i18n/zh'

import { stubThreadEnvironment } from '../test-utils'

import { Thread } from '.'

stubThreadEnvironment()
afterEach(cleanup)

const createdAt = new Date('2026-05-01T00:00:00.000Z')

const messages = [
  {
    id: 'user-1',
    role: 'user',
    content: [{ type: 'text', text: '你好' }],
    attachments: [],
    createdAt,
    metadata: { custom: {} }
  },
  {
    id: 'assistant-error-1',
    role: 'assistant',
    content: [],
    status: { type: 'incomplete', reason: 'error', error: 'HTTP 401: invalid api key' },
    createdAt,
    metadata: {
      unstable_state: null,
      unstable_annotations: [],
      unstable_data: [],
      steps: [],
      custom: {
        errorSurface: {
          apiKeyEnv: 'OPENAI_API_KEY',
          authKind: 'api_key',
          code: 'auth',
          layer: 'auth',
          provider: 'openai',
          providerLabel: 'OpenAI',
          retryable: false
        }
      }
    }
  }
] as unknown as ThreadMessage[]

function Harness() {
  const runtime = useExternalStoreRuntime<ThreadMessage>({ messages, isRunning: false, onNew: async () => {} })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Thread />
    </AssistantRuntimeProvider>
  )
}

it('renders the rejected-key card heading, body, key button and details toggle in Chinese', async () => {
  render(
    <I18nProvider configClient={null} initialLocale="zh">
      <MemoryRouter>
        <Harness />
      </MemoryRouter>
    </I18nProvider>
  )

  const enThread = en.assistant.thread
  // The row that was already translated renders, so the card itself is up.
  expect(await screen.findByRole('button', { name: zh.assistant.thread.errorRetry })).toBeTruthy()

  expect(screen.queryByText((enThread.errorAuthKinds.api_key.title as (p: string) => string)('OpenAI'))).toBeNull()
  expect(screen.queryByText((enThread.errorAuthKinds.api_key.body as (p: string) => string)('OpenAI'))).toBeNull()
  expect(screen.queryByRole('button', { name: enThread.errorUpdateApiKey })).toBeNull()
  expect(screen.queryByText(enThread.errorDetails)).toBeNull()

  const zhThread = zh.assistant.thread
  expect(screen.getByText((zhThread.errorAuthKinds.api_key.title as (p: string) => string)('OpenAI'))).toBeTruthy()
  expect(screen.getByText((zhThread.errorAuthKinds.api_key.body as (p: string) => string)('OpenAI'))).toBeTruthy()
  expect(screen.getByRole('button', { name: zhThread.errorUpdateApiKey })).toBeTruthy()
  expect(screen.getByText(zhThread.errorDetails)).toBeTruthy()
})
