export type User = { id: number; email: string; active?: boolean }
type Tokens = { access_token: string; refresh_token: string }
export type AuthState = { status: 'loading' | 'authenticated' | 'anonymous' | 'error'; user: User | null; error: string }
export const STORAGE_KEY = 'quiz.refresh'

export class Session {
  private access = ''
  private refreshToken = ''
  private generation = 0
  private loggingOut = false
  private refreshFlight: Promise<void> | null = null
  private restoreFlight: Promise<void> | null = null
  private listeners = new Set<() => void>()
  private state: AuthState = { status: 'loading', user: null, error: '' }

  private baseUrl: string
  private storage: Storage
  private transport: typeof fetch
  constructor(baseUrl: string, storage: Storage, transport: typeof fetch = fetch) {
    this.baseUrl = baseUrl; this.storage = storage; this.transport = transport
  }

  getSnapshot = () => this.state
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  private publish(state: AuthState) { this.state = state; this.listeners.forEach(listener => listener()) }
  private clear() {
    this.generation++
    this.access = ''; this.refreshToken = ''
    try { this.storage.removeItem(STORAGE_KEY) } catch { /* In-memory sessions also work. */ }
    this.publish({ status: 'anonymous', user: null, error: '' })
  }
  private save(tokens: Tokens) {
    if (!tokens.access_token || !tokens.refresh_token) throw new Error('Сервер вернул некорректную сессию.')
    this.access = tokens.access_token
    this.refreshToken = tokens.refresh_token
    try { this.storage.setItem(STORAGE_KEY, tokens.refresh_token) } catch { /* Reload will require login if storage is blocked. */ }
  }
  private async send(path: string, init: RequestInit = {}) {
    const transport = this.transport
    return transport(`${this.baseUrl}/api/v1${path}`, { ...init, signal: init.signal ? AbortSignal.any([init.signal, AbortSignal.timeout(20000)]) : AbortSignal.timeout(20000) })
  }
  private async profile() {
    const response = await this.send('/users/me', { headers: { Authorization: `Bearer ${this.access}` } })
    if (response.status === 401 || response.status === 403) { this.clear(); throw new Error('Войдите в аккаунт заново.') }
    if (!response.ok) throw new Error('Не удалось загрузить профиль. Попробуйте ещё раз.')
    return response.json() as Promise<User>
  }
  refresh = (): Promise<void> => {
    if (this.loggingOut) return Promise.reject(new Error('Выполняется выход.'))
    if (this.refreshFlight) return this.refreshFlight
    const generation = this.generation
    this.refreshFlight = (async () => {
      if (!this.refreshToken) { this.clear(); throw new Error('Войдите в аккаунт.') }
      const response = await this.send('/auth/refresh', { method: 'POST', headers: { Authorization: `Bearer ${this.refreshToken}` } })
      if (generation !== this.generation) throw new Error('Сессия изменилась.')
      if (response.status === 401 || response.status === 403) { this.clear(); throw new Error('Сессия истекла. Войдите снова.') }
      if (!response.ok) throw new Error('Не удалось обновить сессию. Повторите попытку.')
      const tokens: Tokens = await response.json()
      if (generation !== this.generation) throw new Error('Сессия изменилась.')
      this.save(tokens)
    })().finally(() => { this.refreshFlight = null })
    return this.refreshFlight
  }
  restore = (): Promise<void> => {
    if (this.restoreFlight) return this.restoreFlight
    if (this.state.status === 'authenticated' || this.state.status === 'anonymous') return Promise.resolve()
    this.publish({ status: 'loading', user: null, error: '' })
    this.restoreFlight = (async () => {
      try {
        try { this.refreshToken = this.refreshToken || this.storage.getItem(STORAGE_KEY) || '' } catch { /* Browser storage may be unavailable. */ }
        if (!this.refreshToken) { this.clear(); return }
        await this.refresh()
        const generation = this.generation
        const user = await this.profile()
        if (generation === this.generation) this.publish({ status: 'authenticated', user, error: '' })
      } catch {
        if (this.state.status !== 'anonymous') this.publish({ status: 'error', user: null, error: 'Не удалось восстановить вход. Проверьте соединение и повторите попытку.' })
      }
    })().finally(() => { this.restoreFlight = null })
    return this.restoreFlight
  }
  login = async (email: string, password: string) => {
    const response = await this.send('/auth/login', { method: 'POST', body: new URLSearchParams({ username: email.trim(), password }) })
    if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'Неверный email или пароль.' : 'Не удалось войти. Попробуйте позже.')
    this.generation++
    this.save(await response.json())
    try {
      const user = await this.profile()
      this.publish({ status: 'authenticated', user, error: '' })
    } catch (error) { this.clear(); throw error }
  }
  logout = async () => {
    if (this.loggingOut) return
    this.loggingOut = true
    try {
      // Wait for rotation so that logout revokes the latest refresh token.
      if (this.refreshFlight) { try { await this.refreshFlight } catch { /* Still attempt to revoke if available. */ } }
      if (this.refreshToken) {
        const response = await this.send('/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${this.refreshToken}` } })
        if (!response.ok && response.status !== 401 && response.status !== 403) throw new Error('Не удалось выйти. Повторите попытку.')
      }
      this.clear()
    } finally { this.loggingOut = false }
  }
  request = async (path: string, init: RequestInit = {}) => {
    if (this.loggingOut) throw new Error('Выполняется выход.')
    if (!path.startsWith('/') || path.startsWith('//')) throw new Error('Некорректный путь API.')
    const generation = this.generation
    const usedAccess = this.access
    const send = () => {
      const headers = new Headers(init.headers)
      headers.set('Authorization', `Bearer ${this.access}`)
      return this.send(path, { ...init, headers })
    }
    if (!usedAccess) throw new Error('Войдите в аккаунт.')
    let response = await send()
    if (generation !== this.generation) throw new Error('Сессия изменилась.')
    if (response.status === 401) {
      // Another request may already have rotated the token while this one was in flight.
      if (usedAccess === this.access) await this.refresh()
      if (generation !== this.generation) throw new Error('Сессия изменилась.')
      response = await send()
      if (generation !== this.generation) throw new Error('Сессия изменилась.')
      if (response.status === 401) { this.clear(); throw new Error('Сессия истекла. Войдите снова.') }
    }
    return response
  }
}
