import { Session } from '../auth/session'

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
export const apiFetch = session.request
