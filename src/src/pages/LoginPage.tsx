import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { session } from '../api/client'
import { safeReturnPath } from '../auth/returnPath'

export default function LoginPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [pending, setPending] = useState(false)
  const [visible, setVisible] = useState(false)
  const [error, setError] = useState('')
  const from = safeReturnPath(location.state?.from)
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setPending(true); setError('')
    try {
      await session.login(String(data.get('email')), String(data.get('password')))
      navigate(from, { replace: true })
    } catch (error) { setError(error instanceof TypeError ? 'Нет соединения с сервером. Попробуйте ещё раз.' : error instanceof Error ? error.message : 'Не удалось войти.') }
    finally { setPending(false) }
  }
  return <main className="registration-page"><section className="form-panel">
    <h1>Войти в аккаунт</h1>
    {location.state?.registered && <p className="auth-notice" role="status">Аккаунт создан. Войдите с вашим email и паролем.</p>}
    <form onSubmit={login}>
      <label htmlFor="email">Электронная почта</label>
      <input id="email" name="email" type="email" autoComplete="username" defaultValue={location.state?.email ?? ''} required disabled={pending} />
      <label htmlFor="password">Пароль</label>
      <div className="password-field"><input id="password" name="password" type={visible ? 'text' : 'password'} autoComplete="current-password" required disabled={pending} /><button className="visibility" type="button" onClick={() => setVisible(!visible)} aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'} aria-pressed={visible}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" />{visible && <path d="m3 3 18 18" />}</svg></button></div>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="submit auth-submit" disabled={pending}>{pending ? 'Входим…' : 'Войти'}</button>
    </form>
    <Link className="dialog-register" to="/register" state={{ from }}>Создать аккаунт</Link>
    <p className="privacy-link"><Link to="/privacy" target="_blank" rel="noreferrer">Обработка персональных данных</Link></p>
  </section></main>
}
