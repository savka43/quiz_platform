import { Session } from '../auth/session'
import { localApiFetch } from '../data/localStore'

export const LOCAL_MODE = import.meta.env.VITE_DATA_MODE !== 'api'
export const ACCOUNT_APP_URL = (import.meta.env.VITE_ACCOUNT_APP_URL ?? '').replace(/\/$/, '')
export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
// Refresh survives reload in the current tab; access tokens stay in memory.
const tabStorage: Storage = {
  getItem: key => window.sessionStorage.getItem(key),
  setItem: (key, value) => window.sessionStorage.setItem(key, value),
  removeItem: key => window.sessionStorage.removeItem(key),
  clear: () => window.sessionStorage.clear(),
  key: index => window.sessionStorage.key(index),
  get length() { return window.sessionStorage.length },
}
export const session = new Session(API_URL, tabStorage)
export const apiFetch = LOCAL_MODE ? localApiFetch : session.request
export function accountUrl(page: 'login' | 'register') {
  return ACCOUNT_APP_URL ? `${ACCOUNT_APP_URL}/${page}` : ''
}
