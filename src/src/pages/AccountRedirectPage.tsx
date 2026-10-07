import { useEffect } from 'react'
import { Link } from 'react-router'
import { accountUrl } from '../api/client'

export default function AccountRedirectPage({ page }: { page: 'login' | 'register' }) {
  const targetPage = page
  const target = accountUrl(targetPage)
  useEffect(() => { if (target) window.location.replace(target) }, [target])
  if (target) {
    return <main className="registration-page" role="status">Переходим к версии с аккаунтом…</main>
  }
  return <main className="registration-page"><section className="form-panel account-redirect"><p className="home-kicker">АККАУНТНАЯ ВЕРСИЯ</p><h1>{targetPage === 'register' ? 'Регистрация' : 'Вход'}</h1><p>Аккаунты работают на отдельной версии приложения. Укажи её адрес в настройке <code>VITE_ACCOUNT_APP_URL</code>, чтобы включить переход.</p><Link className="submit account-home-link" to="/">Продолжить без аккаунта</Link></section></main>
}
