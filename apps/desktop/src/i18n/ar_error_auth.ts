import type { Translations } from './types'

type ThreadCopy = Translations['assistant']['thread']

// The rejected-credential error card (lib/error-surface-copy.ts): heading, body, key button and details toggle.
export const arErrorAuth: Pick<ThreadCopy, 'errorAuthKinds' | 'errorDetails' | 'errorUpdateApiKey'> = {
  errorAuthKinds: {
    api_key: {
      title: provider => `رفض ${provider} مفتاح API الخاص بك`,
      body: provider => `المفتاح المحفوظ لـ ${provider} غير صالح أو أُلغي. حدّثه ثم أعد المحاولة.`
    },
    oauth: { title: provider => `انتهت صلاحية تسجيل دخولك إلى ${provider}` }
  },
  errorDetails: 'التفاصيل',
  errorUpdateApiKey: 'تحديث مفتاح API'
}
