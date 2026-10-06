import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { apiFetch } from '../api/client'

type FavoriteQuestion = {
  id: number; test_id: number; text: string; question_type: string; correct_answer: string
  options: { text: string; is_correct: boolean }[]
  blanks: { prompt: string; correct_answer: string; choices?: string[] }[]
}

export default function FavoritesPage() {
  const navigate = useNavigate()
  const [questions, setQuestions] = useState<FavoriteQuestion[]>([])
  const [selected, setSelected] = useState<number[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setLoading(true); setError('')
      try {
        const rows: FavoriteQuestion[] = []
        for (let offset = 0; ; offset += 100) {
          const response = await apiFetch(`/users/me/favorites?limit=100&offset=${offset}`, { signal: controller.signal })
          if (!response.ok) throw new Error('Не удалось загрузить избранные вопросы.')
          const page: FavoriteQuestion[] = await response.json()
          rows.push(...page)
          if (page.length < 100) break
        }
        if (!controller.signal.aborted) { setQuestions(rows); setSelected(rows.map(row => row.id)) }
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Нет соединения с сервером.') }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }
    void load()
    return () => controller.abort()
  }, [retry])

  const chosen = useMemo(() => selected.filter(id => questions.some(q => q.id === id)), [selected, questions])
  async function remove(id: number) {
    setBusy(true); setError('')
    try {
      const response = await apiFetch(`/questions/${id}/favorite`, { method: 'DELETE' })
      if (!response.ok) throw new Error('Не удалось убрать вопрос из избранного.')
      setQuestions(rows => rows.filter(q => q.id !== id)); setSelected(rows => rows.filter(value => value !== id))
    } catch (e) { setError(e instanceof Error ? e.message : 'Нет соединения с сервером.') }
    finally { setBusy(false) }
  }
  async function practice() {
    if (!chosen.length || busy) return
    setBusy(true); setError('')
    try {
      const response = await apiFetch('/favorites/attempts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question_ids: chosen }) })
      if (!response.ok) throw new Error(response.status === 403 ? 'Некоторые вопросы больше недоступны. Обнови список.' : 'Не удалось начать повторение.')
      const attempt: { id: number } = await response.json()
      navigate(`/attempts/${attempt.id}`)
    } catch (e) { setError(e instanceof Error ? e.message : 'Нет соединения с сервером.') }
    finally { setBusy(false) }
  }

  return <main className="practice-page collection-page"><Link className="policy-back" to="/">← Мои тесты</Link><header className="collection-heading"><div><p className="home-kicker">ПОВТОРЕНИЕ</p><h1>Избранные вопросы <span>{questions.length}</span></h1></div><Link className="secondary-action" to="/history">История попыток</Link></header>
    <div className="favorite-toolbar"><p>Выбери вопросы, которые хочешь пройти ещё раз.</p><button className="primary-action" disabled={!chosen.length || busy} onClick={() => void practice()}>{busy ? 'Подождите…' : `Повторить выбранные · ${chosen.length}`}</button></div>
    {error && <p className="error" role="alert">{error} <button className="inline-retry" onClick={() => setRetry(v => v + 1)}>Обновить</button></p>}
    {loading && <p role="status">Загружаем избранное…</p>}
    {!loading && !error && questions.length === 0 && <section className="home-empty"><h2>Избранных вопросов пока нет</h2><p>Добавляй вопросы в избранное из разбора ошибок.</p><Link className="empty-link" to="/history">Открыть историю →</Link></section>}
    <div className="favorite-list">{questions.map(question => <article className="favorite-row" key={question.id}><label className="favorite-check"><input type="checkbox" checked={selected.includes(question.id)} onChange={e => setSelected(ids => e.target.checked ? [...ids, question.id] : ids.filter(id => id !== question.id))} /><span className="sr-only">Выбрать вопрос для повторения</span></label><div className="favorite-content"><h2>{question.text}</h2><p>{question.options.filter(o => o.is_correct).map(o => o.text).join(' · ') || question.correct_answer || question.blanks.map(b => b.correct_answer).join(' · ')}</p><small>Тест № {question.test_id}</small></div><button className="favorite-remove" disabled={busy} onClick={() => void remove(question.id)}>Убрать</button></article>)}</div>
  </main>
}
