import type { Unstable_TriggerAdapter, Unstable_TriggerItem } from '@assistant-ui/core'
import { act, cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { HermesGateway } from '@/hermes'
import { queryClient } from '@/lib/query-client'
import type * as GatewayStore from '@/store/gateway'
import { requestGatewayForAgent } from '@/store/gateway'
import { setSessionOwnerHint } from '@/store/session'

import { useAtCompletions } from './use-at-completions'
import { useSlashCompletions } from './use-slash-completions'

vi.mock('@/store/gateway', async importOriginal => ({
  ...(await importOriginal<typeof GatewayStore>()),
  requestGatewayForAgent: vi.fn()
}))

const CATALOG = {
  categories: [{ name: 'Session', pairs: [['/goal', 'Set a goal']] }],
  pairs: [['/goal', 'Set a goal']]
}

type Search = (query: string) => readonly Unstable_TriggerItem[]

function harness(useAdapter: () => { adapter: Unstable_TriggerAdapter }) {
  const api: { search?: Search } = {}

  function Probe() {
    api.search = useAdapter().adapter.search as Search

    return null
  }

  render(<Probe />)

  return api as { search: Search }
}

async function completions(api: { search: Search }, query: string) {
  await act(async () => {
    api.search(query)
    await Promise.resolve()
  })
  await act(async () => {
    await new Promise(resolve => setTimeout(resolve, 120))
  })

  return api.search(query)
}

const labels = (items: readonly Unstable_TriggerItem[]) => items.map(item => item.label)

afterEach(() => {
  cleanup()
  queryClient.clear()
  vi.mocked(requestGatewayForAgent).mockReset()
})

// On a multiplexed local gateway the window's handle is the primary profile's
// socket; it refuses another profile's session_id with not_found, so the
// palette rendered "No matches" in every non-primary window (#141583).
describe('session-scoped completions go to the session owner', () => {
  it('sends commands.catalog and complete.slash for a secondary-profile session to its own route', async () => {
    setSessionOwnerHint('sess-b', { connectionId: 'local', profile: 'profile-b' })
    const ambient = vi.fn().mockRejectedValue(new Error('not_found'))

    vi.mocked(requestGatewayForAgent).mockImplementation(async (_connection, _profile, method) =>
      method === 'commands.catalog' ? CATALOG : { items: [{ text: '/goal', kind: 'command' }] }
    )

    const api = harness(() =>
      useSlashCompletions({ gateway: { request: ambient } as unknown as HermesGateway, sessionId: 'sess-b' })
    )

    expect(labels(await completions(api, ''))).toContain('goal')
    expect(labels(await completions(api, 'go'))).toContain('goal')

    expect(ambient).not.toHaveBeenCalled()
    expect(requestGatewayForAgent).toHaveBeenCalledWith('local', 'profile-b', 'commands.catalog', {
      session_id: 'sess-b'
    })
    expect(requestGatewayForAgent).toHaveBeenCalledWith('local', 'profile-b', 'complete.slash', {
      text: '/go',
      session_id: 'sess-b'
    })
  })

  it('keeps a session-less draft on the ambient handle with its profile scope', async () => {
    const ambient = vi.fn().mockResolvedValue(CATALOG)

    const api = harness(() =>
      useSlashCompletions({ gateway: { request: ambient } as unknown as HermesGateway, profile: 'profile-b' })
    )

    await completions(api, '')

    expect(ambient).toHaveBeenCalledWith('commands.catalog', { profile: 'profile-b' })
    expect(requestGatewayForAgent).not.toHaveBeenCalled()
  })

  it('sends complete.path for a secondary-profile session to its own route', async () => {
    setSessionOwnerHint('sess-path', { connectionId: 'local', profile: 'profile-b' })
    const ambient = vi.fn().mockRejectedValue(new Error('not_found'))

    vi.mocked(requestGatewayForAgent).mockResolvedValue({
      items: [{ text: '@file:src/main.ts', display: 'main.ts', meta: '' }]
    })

    const api = harness(() =>
      useAtCompletions({
        gateway: { request: ambient } as unknown as HermesGateway,
        sessionId: 'sess-path',
        cwd: '/repo'
      })
    )

    const items = await completions(api, 'file:src/m')

    expect(items.map(item => (item.metadata as { rawText?: string }).rawText)).toContain('@file:src/main.ts')
    expect(ambient).not.toHaveBeenCalled()
    expect(requestGatewayForAgent).toHaveBeenCalledWith('local', 'profile-b', 'complete.path', {
      word: '@file:src/m',
      session_id: 'sess-path',
      cwd: '/repo'
    })
  })
})
