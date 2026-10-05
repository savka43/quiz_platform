import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { apiFetch } from '../api/client'
import type { Attempt } from './answers'

export default function OpenAttempts() {
  const [attempts, setAttempts] = useState<Attempt[]>([])
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setError(false)
      try {
        const rows: Attempt[] = []
        for (let offset = 0; ; offset += 100) {
          const response = await apiFetch(`/users/me/attempts?limit=100&offset=${offset}`, { signal: controller.signal })
          if (!response.ok) throw new Error('load')
          const page: Attempt[] = await response.json()
          rows.push(...page.filter(a => !a.finished_at))
          if (page.length < 100) break
        }
        if (!controller.signal.aborted) setAttempts(rows)
      } catch { if (!controller.signal.aborted) setError(true) }
    }
    void load()
    return () => controller.abort()
  }, [retry])
  if (error) return <p className="error" role="alert">Не удалось загрузить начатые попытки. <button onClick={() => setRetry(v => v + 1)}>Повторить</button></p>
  if (!attempts.length) return null
  return <section className="open-attempts" aria-label="Незавершённые попытки"><h2>Продолжить прохождение</h2>{attempts.map(a => <Link key={a.id} to={`/attempts/${a.id}`}><span>{a.test_title}<small>Попытка № {a.id}</small></span><span>Продолжить →</span></Link>)}</section>
}
