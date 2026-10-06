import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { apiFetch } from '../api/client'
import type { Result } from '../practice/answers'
import NotFoundPage from './NotFoundPage'

type Mistake = {
  attempt_question_id: number; question_id: number | null; text: string; question_type: string
  options: { id: number; text: string }[]; blanks: { prompt: string; choices: string[] }[]
  selected_answer: { selected_option_ids: number[]; user_answer: string; blank_answers: string[] } | null
  correct_answer: string; correct_options: { id: number; text: string }[]
  correct_blanks: { prompt: string; correct_answer: string; choices?: string[] }[]; explanation: string
}

export default function AttemptResultPage() {
  const { attemptId } = useParams()
  if (!attemptId || !/^[1-9]\d*$/.test(attemptId)) return <NotFoundPage />
  return <ResultContent key={attemptId} attemptId={attemptId} />
}

function ResultContent({ attemptId }: { attemptId: string }) {
  const [result, setResult] = useState<Result | null>(null)
  const [mistakes, setMistakes] = useState<Mistake[]>([])
  const [favorites, setFavorites] = useState<Record<number, boolean>>({})
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<number | null>(null)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setError('')
      try {
        const [resultResponse, mistakesResponse] = await Promise.all([
          apiFetch(`/attempts/${attemptId}/result`, { signal: controller.signal }),
          apiFetch(`/attempts/${attemptId}/mistakes`, { signal: controller.signal }),
        ])
        if (resultResponse.status === 409 || mistakesResponse.status === 409) throw new Error('Сначала закончи прохождение теста.')
        if (!resultResponse.ok || !mistakesResponse.ok) throw new Error(resultResponse.status === 403 || mistakesResponse.status === 403 ? 'Нет доступа к этой попытке.' : 'Не удалось загрузить результат.')
        const [summary, rows]: [Result, Mistake[]] = await Promise.all([resultResponse.json(), mistakesResponse.json()])
        if (!controller.signal.aborted) { setResult(summary); setMistakes(rows) }
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Нет соединения с сервером.') }
    }
    void load()
    return () => controller.abort()
  }, [attemptId, retry])

  async function toggleFavorite(questionId: number) {
    setBusyId(questionId); setError('')
    const added = !favorites[questionId]
    try {
      const response = await apiFetch(`/questions/${questionId}/favorite`, { method: added ? 'POST' : 'DELETE' })
      if (!response.ok) throw new Error(response.status === 403 ? 'В избранное можно добавить только свой вопрос.' : 'Не удалось изменить избранное.')
      setFavorites(prev => ({ ...prev, [questionId]: added }))
    } catch (e) { setError(e instanceof Error ? e.message : 'Нет соединения с сервером.') }
    finally { setBusyId(null) }
  }

  return <main className="practice-page review-page">
    <Link className="policy-back" to="/history">← История попыток</Link>
    {!result && !error && <p role="status">Загружаем результат…</p>}
    {error && <p className="error" role="alert">{error} <button className="inline-retry" onClick={() => setRetry(v => v + 1)}>Повторить</button></p>}
    {result && <>
      <section className="practice-card result-summary"><p className="home-kicker">РЕЗУЛЬТАТ</p><h1>{result.title}</h1><p className="practice-score">{result.score}%</p><p>{result.correct} правильных · {result.incorrect} ошибок · {result.total} вопросов</p><div className="review-links"><Link className="secondary-action" to={`/attempts/${attemptId}`}>Пройти ещё раз</Link><Link className="secondary-action" to="/history">К истории</Link></div></section>
      <section className="review-section"><div className="home-heading"><div><p className="home-kicker">РАЗБОР</p><h2>Ошибки <span>{mistakes.length}</span></h2></div></div>
        {mistakes.length === 0 ? <div className="home-empty"><h3>Ошибок нет</h3><p>Все ответы правильные. Отличная работа!</p></div> : mistakes.map((item, index) => {
          const picked = item.selected_answer?.selected_option_ids ?? []
          const selected = item.options.filter(option => picked.includes(option.id))
          return <article className="practice-card mistake-card" key={item.attempt_question_id}>
            <p className="home-kicker">ВОПРОС {index + 1}</p><h2>{item.text}</h2>
            {(item.question_type === 'single_choice' || item.question_type === 'multiple_choice') ? <>
              <div className="answer-review"><strong>Твой ответ</strong>{selected.length ? selected.map(o => <p key={o.id}>{o.text}</p>) : <p>Нет ответа</p>}</div>
              <div className="answer-review is-correct"><strong>Правильный ответ</strong>{item.correct_options.map(o => <p key={o.id}>{o.text}</p>)}</div>
            </> : item.question_type === 'text' ? <>
              <div className="answer-review"><strong>Твой ответ</strong><p>{item.selected_answer?.user_answer || 'Нет ответа'}</p></div>
              <div className="answer-review is-correct"><strong>Правильный ответ</strong><p>{item.correct_answer}</p></div>
            </> : <div className="answer-review is-correct"><strong>Правильные ответы</strong>{item.correct_blanks.map((blank, i) => <p key={i}>{blank.prompt || `Поле ${i + 1}`}: {blank.correct_answer}<span className="muted-answer"> · твой: {item.selected_answer?.blank_answers?.[i] || 'нет ответа'}</span></p>)}</div>}
            {item.explanation && <p className="mistake-explanation">{item.explanation}</p>}
            {item.question_id !== null && <button className="favorite-toggle" disabled={busyId === item.question_id} onClick={() => void toggleFavorite(item.question_id!)}>{busyId === item.question_id ? 'Сохраняем…' : favorites[item.question_id] ? '★ В избранном' : '☆ Добавить в избранное'}</button>}
          </article>
        })}
      </section>
    </>}
  </main>
}
