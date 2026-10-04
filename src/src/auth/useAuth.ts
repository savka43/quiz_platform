import { useSyncExternalStore } from 'react'
import { session } from '../api/client'

export function useAuth() {
  return useSyncExternalStore(session.subscribe, session.getSnapshot)
}
