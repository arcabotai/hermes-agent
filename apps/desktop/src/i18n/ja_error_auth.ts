import type { Translations } from './types'

type ThreadCopy = Translations['assistant']['thread']

// The rejected-credential error card (lib/error-surface-copy.ts): heading, body, key button and details toggle.
export const jaErrorAuth: Pick<ThreadCopy, 'errorAuthKinds' | 'errorDetails' | 'errorUpdateApiKey'> = {
  errorAuthKinds: {
    api_key: {
      title: provider => `${provider} が API キーを拒否しました`,
      body: provider =>
        `${provider} に保存されているキーが無効か、取り消されています。キーを更新してから再試行してください。`
    },
    oauth: { title: provider => `${provider} のサインインの有効期限が切れました` }
  },
  errorDetails: '詳細',
  errorUpdateApiKey: 'API キーを更新'
}
