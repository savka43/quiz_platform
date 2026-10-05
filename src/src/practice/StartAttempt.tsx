import { useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { apiFetch } from '../api/client'
import type { Attempt } from './answers'

export default function StartAttempt({ testId }: { testId: number }) {
  const navigate = useNavigate()
  const lock = useRef(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function start() {
    if (lock.current) return
    lock.current = true; setBusy(true); setError('')
    try {
      const response = await apiFetch(`/tests/${testId}/attempts`, { method: 'POST' })
      if (!response.ok) throw new Error(response.status === 422 ? 'Тест ещё не готов: добавь вопросы и правильные ответы в редакторе.' : response.status === 404 ? 'Тест не найден.' : 'Не удалось начать тест. Попробуй ещё раз.')
      const attempt: Attempt = await response.json()
      navigate(`/attempts/${attempt.id}`)
    } catch (e) { setError(e instanceof TypeError ? 'Нет соединения с сервером.' : e instanceof Error ? e.message : 'Не удалось начать тест.') }
    finally { lock.current = false; setBusy(false) }
  }
  return <div className="quiz-start"><button className="primary-action" disabled={busy} onClick={() => void start()}>{busy ? 'Запускаем…' : 'Начать тест →'}</button>{error && <p className="error" role="alert">{error}</p>}</div>
}
