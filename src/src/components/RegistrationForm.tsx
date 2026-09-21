import { useState } from 'react'
import type { FormEvent } from 'react'

function RegistrationForm() {
  const [visible, setVisible] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [registered, setRegistered] = useState(false)

  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const password = String(data.get('password'))
    setError('')
    if (new TextEncoder().encode(password).length > 72) {
      setError('Пароль слишком длинный. Используйте не больше 72 байт — для кириллицы это примерно 36 символов.')
      return
    }
    setPending(true)
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/api/v1/auth/register`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: String(data.get('email')).trim(), password }),
      })
      if (!response.ok) {
        setError(response.status === 409 ? 'Этот email уже зарегистрирован. Используйте другой адрес.' : response.status === 422 ? 'Проверьте email и пароль: нужно не меньше 8 символов.' : 'Не получилось создать аккаунт. Попробуйте чуть позже.')
        return
      }
      setRegistered(true)
    } catch {
      setError('Не удалось связаться с сервером. Проверьте соединение и попробуйте ещё раз.')
    } finally { setPending(false) }
  }

  return (
        <section className="form-panel" aria-labelledby="form-title">
          {registered ? <div className="success" role="status"><span className="success-icon">✓</span><h1 id="form-title">Аккаунт создан</h1><p>Всё получилось. Теперь ты можешь войти с указанным email и паролем.</p></div> : <>
            <h1 id="form-title">Создать аккаунт</h1>
            <form onSubmit={register}>
              <label htmlFor="email">Электронная почта</label>
              <input id="email" name="email" type="email" autoComplete="email" placeholder="you@example.com" required maxLength={255} disabled={pending} />
              <label htmlFor="password">Пароль</label>
              <div className="password-field"><input id="password" name="password" type={visible ? 'text' : 'password'} autoComplete="new-password" placeholder="Придумай надёжный пароль" minLength={8} maxLength={72} aria-describedby="password-hint" required disabled={pending} /><button className="visibility" type="button" aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'} aria-pressed={visible} onClick={() => setVisible(!visible)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" />{visible && <path d="m3 3 18 18" />}</svg></button></div>
              <p id="password-hint" className="hint">Не меньше 8 символов</p>
              {error && <p className="error" role="alert">{error}</p>}
              <button className="submit" type="submit" disabled={pending}>{pending ? 'Создаём аккаунт…' : 'Создать аккаунт'}</button>
            </form>
          </>}
          <p className="privacy-link"><a href="/privacy" target="_blank" rel="noreferrer">Обработка персональных данных<span className="sr-only"> (откроется в новой вкладке)</span></a></p>
        </section>
  )
}

export default RegistrationForm
