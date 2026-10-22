import type { Translations } from './types'

type ThreadCopy = Translations['assistant']['thread']

// The rejected-credential error card (lib/error-surface-copy.ts): heading, body, key button and details toggle.
export const zhErrorAuth: Pick<ThreadCopy, 'errorAuthKinds' | 'errorDetails' | 'errorUpdateApiKey'> = {
  errorAuthKinds: {
    api_key: {
      title: provider => `${provider} 拒绝了你的 API 密钥`,
      body: provider => `为 ${provider} 保存的密钥无效或已被撤销。请更新后重试。`
    },
    oauth: { title: provider => `你的 ${provider} 登录已过期` }
  },
  errorDetails: '详情',
  errorUpdateApiKey: '更新 API 密钥'
}
