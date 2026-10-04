import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'
import { session } from '../api/client'
import { useAuth } from './useAuth'

export function AuthBoundary() {
  const auth = useAuth()
  useEffect(() => { void session.restore() }, [])
  if (auth.status === 'loading') return <main className="registration-page" role="status">Восстанавливаем вход…</main>
  if (auth.status === 'error') return <main className="registration-page"><section className="form-panel"><p role="alert">{auth.error}</p><button className="submit" onClick={() => void session.restore()}>Повторить</button></section></main>
  return <Outlet />
}

export function RequireAuth() {
  const auth = useAuth()
  const location = useLocation()
  return auth.status === 'authenticated' ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname + location.search + location.hash }} />
}

export function GuestOnly() {
  const auth = useAuth()
  return auth.status === 'authenticated' ? <Navigate to="/" replace /> : <Outlet />
}

