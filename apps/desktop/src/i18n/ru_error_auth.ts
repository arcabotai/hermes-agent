import type { Translations } from './types'

type ThreadCopy = Translations['assistant']['thread']

// The rejected-credential error card (lib/error-surface-copy.ts): heading, body, key button and details toggle.
export const ruErrorAuth: Pick<
  ThreadCopy,
  'errorAuthKinds' | 'errorDetails' | 'errorOauthExpired' | 'errorUpdateApiKey'
> = {
  errorAuthKinds: {
    api_key: {
      title: provider => `${provider} отклонил ваш API-ключ`,
      body: provider =>
        `Ключ, сохранённый для ${provider}, недействителен или был отозван. Обновите его и повторите попытку.`
    },
    oauth: { title: provider => `Срок действия входа в ${provider} истёк` }
  },
  errorDetails: 'Подробнее',
  errorOauthExpired: provider =>
    `Сеанс входа в ${provider} истёк или был отозван. Войдите снова, чтобы продолжить разговор.`,
  errorUpdateApiKey: 'Обновить API-ключ'
}
