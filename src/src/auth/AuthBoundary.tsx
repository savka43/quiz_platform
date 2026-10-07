import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'
import { LOCAL_MODE, session } from '../api/client'
import { useAuth } from './useAuth'

export function AuthBoundary() {
  const auth = useAuth()
  useEffect(() => { if (!LOCAL_MODE) void session.restore() }, [])
  if (LOCAL_MODE) return <Outlet />
  if (auth.status === 'loading') return <main className="registration-page" role="status">Восстанавливаем вход…</main>
  if (auth.status === 'error') return <main className="registration-page"><section className="form-panel"><p role="alert">{auth.error}</p><button className="submit" onClick={() => void session.restore()}>Повторить</button></section></main>
  return <Outlet />
}

export function RequireAuth() {
  const auth = useAuth()
  const location = useLocation()
  return LOCAL_MODE || auth.status === 'authenticated' ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname + location.search + location.hash }} />
}

export function GuestOnly() {
  const auth = useAuth()
  return !LOCAL_MODE && auth.status === 'authenticated' ? <Navigate to="/" replace /> : <Outlet />
}
