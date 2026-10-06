import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { apiFetch } from '../api/client'
import type { Attempt } from '../practice/answers'

export default function HistoryPage() {
  const [attempts, setAttempts] = useState<Attempt[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setLoading(true); setError('')
      try {
        const rows: Attempt[] = []
        for (let offset = 0; ; offset += 100) {
          const response = await apiFetch(`/users/me/attempts?limit=100&offset=${offset}`, { signal: controller.signal })
          if (!response.ok) throw new Error('Не удалось загрузить историю попыток.')
          const page: Attempt[] = await response.json()
          rows.push(...page)
          if (page.length < 100) break
        }
        if (!controller.signal.aborted) setAttempts(rows)
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Нет соединения с сервером.') }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }
    void load()
    return () => controller.abort()
  }, [retry])

  return <main className="practice-page collection-page"><Link className="policy-back" to="/">← Мои тесты</Link><header className="collection-heading"><div><p className="home-kicker">ТВОИ ПРОХОЖДЕНИЯ</p><h1>История <span>{attempts.length}</span></h1></div><Link className="secondary-action" to="/favorites">Избранные вопросы</Link></header>
    {loading && <p role="status">Загружаем историю…</p>}
    {error && <p className="error" role="alert">{error} <button className="inline-retry" onClick={() => setRetry(v => v + 1)}>Повторить</button></p>}
    {!loading && !error && attempts.length === 0 && <section className="home-empty"><h2>Пока нет попыток</h2><p>Начни прохождение одного из своих тестов.</p><Link className="empty-link" to="/">К моим тестам →</Link></section>}
    <div className="history-list">{attempts.map(attempt => <article className="history-row" key={attempt.id}><div><h2>{attempt.test_title}</h2><p>{new Date(attempt.started_at).toLocaleString('ru-RU')}</p></div><div className="history-result">{attempt.finished_at ? <><strong>{attempt.score}%</strong><Link to={`/attempts/${attempt.id}/result`}>Разобрать →</Link></> : <><span className="attempt-open-label">Не завершён</span><Link to={`/attempts/${attempt.id}`}>Продолжить →</Link></>}</div></article>)}</div>
  </main>
}
