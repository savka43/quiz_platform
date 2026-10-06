import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { apiFetch } from '../api/client'
import AnswerFields from '../practice/AnswerFields'
import { answerBody, answerError, emptyAnswer, sameAnswer } from '../practice/answers'
import type { Answer, Attempt, PracticeQuestion, Result, SavedAnswer } from '../practice/answers'
import NotFoundPage from './NotFoundPage'

async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await apiFetch(path, { signal })
  if (!response.ok) throw new Error(response.status === 403 ? 'Нет доступа к этой попытке.' : response.status === 404 ? 'Попытка не найдена.' : 'Не удалось загрузить попытку. Попробуй ещё раз.')
  return response.json()
}

export default function AttemptPage() {
  const { attemptId } = useParams()
  if (!attemptId || !/^[1-9]\d*$/.test(attemptId)) return <NotFoundPage />
  return <Practice key={attemptId} attemptId={attemptId} />
}

function Practice({ attemptId }: { attemptId: string }) {
  const [params, setParams] = useSearchParams()
  const [attempt, setAttempt] = useState<Attempt | null>(null)
  const [questions, setQuestions] = useState<PracticeQuestion[]>([])
  const [answers, setAnswers] = useState<Record<number, Answer>>({})
  const [saved, setSaved] = useState<Record<number, Answer>>({})
  const [result, setResult] = useState<Result | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  const lock = useRef(false)
  const titleRef = useRef<HTMLHeadingElement>(null)
  const requested = Number(params.get('q') ?? '1')
  const index = Number.isInteger(requested) && requested > 0 ? Math.min(requested - 1, Math.max(0, questions.length - 1)) : 0
  const question = questions[index]
  const current = question ? answers[question.attempt_question_id] ?? emptyAnswer(question) : null
  const dirty = questions.some(q => answers[q.attempt_question_id] && !sameAnswer(q, answers[q.attempt_question_id], saved[q.attempt_question_id]))
  const savedCount = questions.filter(q => saved[q.attempt_question_id]).length

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setLoading(true); setError('')
      try {
        const meta = await read<Attempt>(`/attempts/${attemptId}`, controller.signal)
        if (meta.finished_at) {
          const summary = await read<Result>(`/attempts/${attemptId}/result`, controller.signal)
          if (!controller.signal.aborted) { setAttempt(meta); setResult(summary) }
        } else {
          const [rows, stored] = await Promise.all([read<PracticeQuestion[]>(`/attempts/${attemptId}/questions`, controller.signal), read<SavedAnswer[]>(`/attempts/${attemptId}/answers`, controller.signal)])
          if (!rows.length) throw new Error('В попытке нет вопросов.')
          const byId = Object.fromEntries(stored.map(a => [a.attempt_question_id, { selected_option_ids: a.selected_option_ids, user_answer: a.user_answer, blank_answers: a.blank_answers }]))
          if (!controller.signal.aborted) { setAttempt(meta); setQuestions(rows); setAnswers(byId); setSaved(byId) }
        }
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Нет соединения.') }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }
    void load()
    return () => controller.abort()
  }, [attemptId, retry])

  useEffect(() => {
    if (!dirty || attempt?.finished_at) return
    function warn(event: BeforeUnloadEvent) { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty, attempt?.finished_at])

  function go(to: number) { setParams({ q: String(to + 1) }, { replace: true }); requestAnimationFrame(() => titleRef.current?.focus()) }
  async function saveQuestion(q: PracticeQuestion, answer: Answer) {
    const issue = answerError(q, answer)
    if (issue) throw new Error(issue)
    if (sameAnswer(q, answer, saved[q.attempt_question_id])) return
    const response = await apiFetch(`/attempts/${attemptId}/answers`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(answerBody(q, answer)) })
    if (!response.ok) {
      if (response.status === 409) {
        const meta = await read<Attempt>(`/attempts/${attemptId}`)
        if (meta.finished_at) { setAttempt(meta); setResult(await read<Result>(`/attempts/${attemptId}/result`)); return }
      }
      throw new Error(response.status === 422 ? 'Проверь ответ на вопрос.' : 'Ответ не сохранён. Повтори попытку.')
    }
    const stored: SavedAnswer = await response.json()
    const clean = { selected_option_ids: stored.selected_option_ids, user_answer: stored.user_answer, blank_answers: stored.blank_answers }
    setSaved(prev => ({ ...prev, [q.attempt_question_id]: clean }))
    setAnswers(prev => ({ ...prev, [q.attempt_question_id]: clean }))
  }

  async function act(action: 'save' | 'next' | 'finish') {
    if (lock.current || !question || !current) return
    lock.current = true; setBusy(true); setError('')
    try {
      if (action === 'finish') {
        const missing = questions.findIndex(q => answerError(q, answers[q.attempt_question_id] ?? emptyAnswer(q)))
        if (missing !== -1) { go(missing); throw new Error('Перед завершением ответь на все вопросы.') }
        for (const q of questions) await saveQuestion(q, answers[q.attempt_question_id])
        const response = await apiFetch(`/attempts/${attemptId}/finish`, { method: 'POST' })
        if (!response.ok && response.status !== 409) throw new Error('Не удалось завершить попытку. Попробуй ещё раз.')
        const meta = await read<Attempt>(`/attempts/${attemptId}`)
        if (!meta.finished_at) throw new Error('Не все ответы сохранены. Проверь вопросы и повтори завершение.')
        setAttempt(meta)
        setResult(await read<Result>(`/attempts/${attemptId}/result`))
      } else {
        await saveQuestion(question, current)
        if (action === 'next') go(Math.min(index + 1, questions.length - 1))
      }
    } catch (e) { setError(e instanceof TypeError ? 'Нет соединения. Введённые ответы остались на странице — попробуй сохранить ещё раз.' : e instanceof Error ? e.message : 'Не удалось сохранить ответ.') }
    finally { lock.current = false; setBusy(false) }
  }

  return <main className="practice-page">
    <Link className="policy-back" to="/" onClick={e => { if (busy || (dirty && !attempt?.finished_at && !window.confirm('Есть несохранённые ответы. Выйти к тестам?'))) e.preventDefault() }}>← Мои тесты</Link>
    {loading ? <p role="status">Загружаем попытку…</p> : result ? <section className="practice-card practice-complete"><span className="success-icon">✓</span><p className="home-kicker">ПОПЫТКА ЗАВЕРШЕНА</p><h1>{result.title}</h1><p className="practice-score">{result.score}%</p><p>Правильных ответов: {result.correct} из {result.total}</p><Link className="primary-action" to={`/attempts/${attemptId}/result`}>Посмотреть ошибки</Link><Link className="secondary-action result-home-link" to="/">К моим тестам</Link></section> : !attempt || !question || attempt.finished_at ? <section className="practice-card"><p role="alert">{error || 'Не удалось загрузить результат.'}</p><button className="secondary-action" onClick={() => setRetry(v => v + 1)}>Повторить</button></section> : <>
      <header className="practice-heading"><p className="home-kicker">ПРОХОЖДЕНИЕ</p><h1>{attempt.test_title}</h1><div className="practice-progress-label"><span>Вопрос {index + 1} из {questions.length}</span><span>Сохранено {savedCount} из {questions.length}</span></div><progress max={questions.length} value={savedCount} aria-label="Сохранённые ответы" /></header>
      <nav className="practice-map" aria-label="Вопросы теста">{questions.map((q, i) => <button key={q.attempt_question_id} type="button" disabled={busy} aria-current={i === index ? 'step' : undefined} aria-label={`Вопрос ${i + 1}${saved[q.attempt_question_id] ? ', сохранён' : ''}`} className={`${i === index ? 'current' : ''} ${saved[q.attempt_question_id] ? 'answered' : ''}`} onClick={() => { go(i); setError('') }}>{i + 1}</button>)}</nav>
      <section className="practice-card"><h2 ref={titleRef} tabIndex={-1}>{question.text}</h2><fieldset className="practice-fields" disabled={busy}><legend className="sr-only">Ответ на вопрос {index + 1}</legend><AnswerFields key={question.attempt_question_id} question={question} answer={current!} onChange={answer => { setAnswers(prev => ({ ...prev, [question.attempt_question_id]: answer })); setError('') }} /></fieldset>
        <p className="practice-save-state" role="status">{busy ? 'Сохраняем…' : sameAnswer(question, current!, saved[question.attempt_question_id]) ? 'Ответ сохранён' : 'Ответ сохраняется по кнопке ниже'}</p>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="practice-controls"><button className="secondary-action" disabled={busy || index === 0} onClick={() => { go(index - 1); setError('') }}>Назад</button><button className="secondary-action" disabled={busy} onClick={() => void act('save')}>Сохранить ответ</button>{index < questions.length - 1 && <button className="primary-action" disabled={busy} onClick={() => void act('next')}>Сохранить и дальше →</button>}</div>
      </section>
      <div className="practice-finish"><p>До завершения можно вернуться к любому вопросу и изменить ответ.</p><button className="primary-action" disabled={busy} onClick={() => void act('finish')}>Завершить тест</button></div>
    </>}
  </main>
}
