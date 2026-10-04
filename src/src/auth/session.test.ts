import { describe, expect, it, vi } from 'vitest'
import { Session, STORAGE_KEY } from './session'

function storage(): Storage {
  const values = new Map<string, string>()
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => { values.set(key, value) }, removeItem: key => { values.delete(key) }, clear: () => values.clear(), key: i => [...values.keys()][i] ?? null, get length() { return values.size } }
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const user = { id: 1, email: 'test@example.com' }
const tokens = { access_token: 'access1', refresh_token: 'refresh1' }
const rotated = { access_token: 'access2', refresh_token: 'refresh2' }
const pathOf = (url: RequestInfo | URL) => String(url).split('/api/v1')[1]

function setup(handler?: (url: RequestInfo | URL, init?: RequestInit) => Promise<Response>) {
  const store = storage()
  const fetcher = vi.fn<typeof fetch>(handler ?? (async url => pathOf(url) === '/auth/login' ? json(tokens) : json(user)))
  return { store, fetcher, auth: new Session('http://localhost:8000', store, fetcher) }
}

describe('browser auth session', () => {
  it('starts anonymous without stored credentials', async () => {
    const { auth, fetcher } = setup()
    await auth.restore()
    expect(auth.getSnapshot().status).toBe('anonymous')
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('logs in and stores only refresh, never password or access', async () => {
    const { auth, store } = setup()
    await auth.login('test@example.com', 'password123')
    expect(auth.getSnapshot().user).toEqual(user)
    expect(store.length).toBe(1)
    expect(store.getItem(STORAGE_KEY)).toBe('refresh1')
  })
  it('restores a reloaded tab and deduplicates StrictMode initialization', async () => {
    const { auth, store, fetcher } = setup(async url => pathOf(url) === '/auth/refresh' ? json(rotated) : json(user))
    store.setItem(STORAGE_KEY, 'refresh1')
    await Promise.all([auth.restore(), auth.restore()])
    expect(fetcher.mock.calls.filter(([url]) => pathOf(url) === '/auth/refresh')).toHaveLength(1)
    expect(auth.getSnapshot().status).toBe('authenticated')
    expect(store.getItem(STORAGE_KEY)).toBe('refresh2')
  })
  it('refreshes once for concurrent 401s, and retries with the new token', async () => {
    const { auth, fetcher } = setup(async (url, init) => {
      if (pathOf(url) === '/auth/login') return json(tokens)
      if (pathOf(url) === '/users/me') return json(user)
      if (pathOf(url) === '/auth/refresh') return json(rotated)
      return new Headers(init?.headers).get('Authorization') === 'Bearer access2' ? json([]) : json({}, 401)
    })
    await auth.login(user.email, 'password123')
    const responses = await Promise.all([auth.request('/tests/'), auth.request('/questions/')])
    expect(responses.map(r => r.status)).toEqual([200, 200])
    expect(fetcher.mock.calls.filter(([url]) => pathOf(url) === '/auth/refresh')).toHaveLength(1)
  })
  it('clears rejected refresh tokens', async () => {
    const { auth, store } = setup(async () => json({}, 401))
    store.setItem(STORAGE_KEY, 'revoked')
    await auth.restore()
    expect(auth.getSnapshot().status).toBe('anonymous')
    expect(store.getItem(STORAGE_KEY)).toBeNull()
  })
  it('preserves the session on connection failures and allows retry', async () => {
    const { auth, store, fetcher } = setup()
    store.setItem(STORAGE_KEY, 'refresh1')
    fetcher.mockRejectedValueOnce(new TypeError('offline'))
    await auth.restore()
    expect(auth.getSnapshot().status).toBe('error')
    expect(store.getItem(STORAGE_KEY)).toBe('refresh1')
    fetcher.mockImplementation(async url => pathOf(url) === '/auth/refresh' ? json(rotated) : json(user))
    await auth.restore()
    expect(auth.getSnapshot().status).toBe('authenticated')
  })
  it('revokes refresh on logout and clears local state', async () => {
    const { auth, store, fetcher } = setup(async url => pathOf(url) === '/auth/logout' ? new Response(null, { status: 204 }) : pathOf(url) === '/auth/login' ? json(tokens) : json(user))
    await auth.login(user.email, 'password123')
    await auth.logout()
    const call = fetcher.mock.calls.find(([url]) => pathOf(url) === '/auth/logout')!
    expect(new Headers(call[1]?.headers).get('Authorization')).toBe('Bearer refresh1')
    expect(auth.getSnapshot().status).toBe('anonymous')
    expect(store.length).toBe(0)
  })
  it('does not pretend to revoke a session when logout is offline', async () => {
    const { auth, fetcher } = setup()
    await auth.login(user.email, 'password123')
    fetcher.mockRejectedValueOnce(new TypeError('offline'))
    await expect(auth.logout()).rejects.toThrow()
    expect(auth.getSnapshot().status).toBe('authenticated')
  })
  it('does not refresh for a forbidden resource', async () => {
    const { auth, fetcher } = setup()
    await auth.login(user.email, 'password123')
    fetcher.mockResolvedValueOnce(json({}, 403))
    expect((await auth.request('/tests/2')).status).toBe(403)
    expect(auth.getSnapshot().status).toBe('authenticated')
  })
  it('does not loop if the retried request still returns 401', async () => {
    const { auth, fetcher } = setup()
    await auth.login(user.email, 'password123')
    fetcher.mockResolvedValueOnce(json({}, 401)).mockResolvedValueOnce(json(rotated)).mockResolvedValueOnce(json({}, 401))
    await expect(auth.request('/tests/')).rejects.toThrow('Сессия истекла')
    expect(auth.getSnapshot().status).toBe('anonymous')
    expect(fetcher).toHaveBeenCalledTimes(5)
  })
  it('logout waits for refresh rotation and revokes the rotated token', async () => {
    let resolveRefresh!: (value: Response) => void
    const { auth, fetcher } = setup(async url => {
      if (pathOf(url) === '/auth/login') return json(tokens)
      if (pathOf(url) === '/auth/refresh') return new Promise(resolve => { resolveRefresh = resolve })
      if (pathOf(url) === '/auth/logout') return new Response(null, { status: 204 })
      return json(user)
    })
    await auth.login(user.email, 'password123')
    const refreshing = auth.refresh()
    const loggingOut = auth.logout()
    resolveRefresh(json(rotated))
    await Promise.all([refreshing, loggingOut])
    const call = fetcher.mock.calls.find(([url]) => pathOf(url) === '/auth/logout')!
    expect(new Headers(call[1]?.headers).get('Authorization')).toBe('Bearer refresh2')
    expect(auth.getSnapshot().status).toBe('anonymous')
  })
})

it('calls native fetch without an incompatible receiver', async () => {
  const transport: typeof fetch = async function (this: unknown, url) {
    expect(this).toBeUndefined()
    return pathOf(url) === '/auth/login' ? json(tokens) : json(user)
  }
  const auth = new Session('http://localhost:8000', storage(), transport)
  await auth.login(user.email, 'password123')
  expect(auth.getSnapshot().status).toBe('authenticated')
})

it('does not revive state from a request completing after logout', async () => {
  let resolveRequest!: (value: Response) => void
  const { auth } = setup(async url => {
    if (pathOf(url) === '/auth/login') return json(tokens)
    if (pathOf(url) === '/users/me') return json(user)
    if (pathOf(url) === '/auth/logout') return new Response(null, { status: 204 })
    return new Promise(resolve => { resolveRequest = resolve })
  })
  await auth.login(user.email, 'password123')
  const request = auth.request('/tests/')
  await auth.logout()
  resolveRequest(json({}, 401))
  await expect(request).rejects.toThrow('Сессия изменилась')
  expect(auth.getSnapshot().status).toBe('anonymous')
})
