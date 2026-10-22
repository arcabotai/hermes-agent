import type { Translations } from './types'

type ThreadCopy = Translations['assistant']['thread']

// The rejected-credential error card (lib/error-surface-copy.ts): heading, body, key button and details toggle.
export const zhHantErrorAuth: Pick<ThreadCopy, 'errorAuthKinds' | 'errorDetails' | 'errorUpdateApiKey'> = {
  errorAuthKinds: {
    api_key: {
      title: provider => `${provider} 拒絕了你的 API 金鑰`,
      body: provider => `為 ${provider} 儲存的金鑰無效或已被撤銷。請更新後重試。`
    },
    oauth: { title: provider => `你的 ${provider} 登入已過期` }
  },
  errorDetails: '詳細資訊',
  errorUpdateApiKey: '更新 API 金鑰'
}
