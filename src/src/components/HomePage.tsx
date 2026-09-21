import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

type ImportQuestion = { text: string; question_type: string; options: { text: string; is_correct: boolean | null }[]; correct_answer: string; blanks: { prompt: string; correct_answer: string; choices?: string[] }[]; explanation: string }
type ImportDocument = { title: string; questions: ImportQuestion[] }
type Quiz = { id: number; title: string; description: string; created_at: string }
const api = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function HomePage() {
  const [token, setToken] = useState('')
  const [tests, setTests] = useState<Quiz[]>([])
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('newest')
  const [modal, setModal] = useState<'login' | 'create' | 'import' | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [revision, setRevision] = useState(0)
  const [preview, setPreview] = useState<ImportDocument | null>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  useEffect(() => { if (modal) dialogRef.current?.showModal() }, [modal])
  const [format, setFormat] = useState('html')

  useEffect(() => {
    if (!token) return
    const controller = new AbortController()
    async function load() {
      setLoading(true)
      setError('')
      try {
        const all: Quiz[] = []
        for (let offset = 0; ; offset += 100) {
          const response = await fetch(`${api}/api/v1/tests/?limit=100&offset=${offset}`, { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal })
          if (!response.ok) throw new Error(response.status === 401 ? 'Сессия истекла. Войдите ещё раз.' : 'Не удалось загрузить тесты.')
          const page: Quiz[] = await response.json()
          all.push(...page)
          if (page.length < 100) break
        }
        setTests(all)
      } catch (e) {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Нет соединения с сервером.')
      } finally { if (!controller.signal.aborted) setLoading(false) }
    }
    void load()
    return () => controller.abort()
  }, [token, revision])

  function open(next: 'login' | 'create' | 'import') {
    setError(''); setPreview(null); setModal(token ? next : 'login')
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true); setError('')
    try {
      let path = '/auth/login'
      let body: BodyInit
      const headers: Record<string, string> = {}
      if (modal === 'login') body = new URLSearchParams({ username: String(data.get('email')), password: String(data.get('password')) })
      else {
        headers.Authorization = `Bearer ${token}`
        if (modal === 'create') {
          path = '/tests/'
          headers['Content-Type'] = 'application/json'
          body = JSON.stringify({ title: data.get('title'), description: data.get('description') })
        } else if (preview) {
          path = `/import/${format}/confirm`
          headers['Content-Type'] = 'application/json'
          body = JSON.stringify(preview)
        } else {
          const file = data.get('file') as File
          if (file.size > 8 * 1024 * 1024) throw new Error('Максимальный размер файла — 8 МБ.')
          const kind = file.name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'html'
          setFormat(kind)
          path = `/import/${kind}/preview`
          body = data
        }
      }
      const response = await fetch(`${api}/api/v1${path}`, { method: 'POST', headers, body })
      if (!response.ok) throw new Error(response.status === 401 ? 'Проверьте email и пароль или войдите заново.' : response.status === 422 ? 'Проверьте данные. У каждого вопроса должны быть указаны правильные ответы.' : 'Не получилось выполнить действие. Попробуйте ещё раз.')
      const result = await response.json()
      if (modal === 'login') setToken(result.access_token)
      if (modal === 'import' && !preview) {
        setPreview({ title: result.title, questions: result.questions.map((q: ImportQuestion) => ({ text: q.text, question_type: q.question_type, options: q.options, correct_answer: q.correct_answer, blanks: q.blanks, explanation: q.explanation })) })
        return
      }
      setModal(null); setRevision(value => value + 1)
    } catch (e) { setError(e instanceof SyntaxError ? 'Проверьте формат документа: некорректный JSON.' : e instanceof Error ? e.message : 'Нет соединения с сервером.') }
    finally { setBusy(false) }
  }

  function updateQuestion(index: number, change: Partial<ImportQuestion>) {
    setPreview(current => current ? { ...current, questions: current.questions.map((q, i) => i === index ? { ...q, ...change } : q) } : current)
  }

  const filtered = tests.filter(test => test.title.toLowerCase().includes(query.toLowerCase())).sort((a, b) => sort === 'title' ? a.title.localeCompare(b.title, 'ru') : sort === 'oldest' ? a.id - b.id : b.id - a.id)

  return <div className="home">
    <header className="home-header"><a className="home-logo" href="/">quiz<span>.</span></a><span className="home-space">Личное пространство</span><button className="account-button" onClick={() => { if (token) { setToken(''); setTests([]); setError('') } else open('login') }}>{token ? 'Выйти' : 'Войти'}<span aria-hidden="true">↗</span></button></header>
    <main className="home-content">
      <div className="home-heading"><div><p className="home-kicker">БИБЛИОТЕКА</p><h1>Мои тесты<span>{tests.length.toString().padStart(2, '0')}</span></h1></div><div className="home-actions"><button className="secondary-action" onClick={() => open('import')}><span aria-hidden="true">↑</span> Импортировать</button><button className="primary-action" onClick={() => open('create')}><span aria-hidden="true">+</span> Создать тест</button></div></div>
      <div className="home-toolbar"><div className="home-search"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" /></svg><input aria-label="Поиск тестов" placeholder="Найти тест" value={query} onChange={e => setQuery(e.target.value)} /></div><select aria-label="Сортировка" value={sort} onChange={e => setSort(e.target.value)}><option value="newest">Сначала новые</option><option value="oldest">Сначала старые</option><option value="title">По названию</option></select></div>
      {error && !modal && <div className="error" role="alert">{error} <button onClick={() => token ? setRevision(v => v + 1) : open('login')}>Повторить</button></div>}
      {loading ? <div className="home-empty" role="status">Загружаем тесты…</div> : filtered.length ? <div className="quiz-grid">{filtered.map(test => <article className="quiz-card" key={test.id}><div className="quiz-card-top"><span className="quiz-mark" aria-hidden="true">≡</span><span>{new Date(test.created_at).toLocaleDateString('ru-RU')}</span></div><h2>{test.title}</h2><p>{test.description || 'Без описания'}</p><span className="quiz-private">Личный тест</span></article>)}</div> : <section className="home-empty"><div className="empty-drawing" aria-hidden="true"><div className="paper-back" /><div className="paper-front"><span /><span /><i>✓</i></div></div><h2>{query ? 'Ничего не нашлось' : token ? 'Здесь будут твои тесты' : 'Твоя библиотека тестов'}</h2><p>{query ? 'Попробуй другое название.' : token ? 'Создай первый тест или загрузи готовый файл.' : 'Войди, чтобы открыть свои тесты.'}</p><button className="empty-link" onClick={() => query ? setQuery('') : open(token ? 'create' : 'login')}>{query ? 'Сбросить поиск' : token ? 'Создать первый тест' : 'Войти в аккаунт'} <span aria-hidden="true">→</span></button></section>}
      <div className="home-bottom"><span><span aria-hidden="true">▣</span> Видно только тебе</span><span>PDF и HTML · до 8 МБ</span></div>
    </main>
    <footer className="home-footer"><span>quiz.</span><a href="/privacy">Обработка персональных данных</a></footer>
    {modal && <div className="modal-backdrop" onClick={e => { if (e.target === e.currentTarget && !busy) setModal(null) }}><dialog ref={dialogRef} onCancel={e => { e.preventDefault(); if (!busy) setModal(null) }} className="home-dialog" aria-labelledby="dialog-title" onKeyDown={e => { if (e.key === 'Escape' && !busy) setModal(null) }}><button className="dialog-close" aria-label="Закрыть" disabled={busy} onClick={() => setModal(null)}>×</button><h2 id="dialog-title">{modal === 'login' ? 'Войти в аккаунт' : modal === 'create' ? 'Новый тест' : preview ? 'Проверить импорт' : 'Импортировать тест'}</h2><form onSubmit={submit}>{modal === 'login' ? <><label htmlFor="login-email">Email</label><input id="login-email" name="email" type="email" autoComplete="email" required /><label htmlFor="login-password">Пароль</label><input id="login-password" name="password" type="password" autoComplete="current-password" required /></> : modal === 'create' ? <><label htmlFor="title">Название</label><input id="title" name="title" maxLength={200} required placeholder="Например, основы Python" /><label htmlFor="description">Описание</label><textarea id="description" name="description" maxLength={20000} rows={3} /></> : preview ? <><label htmlFor="import-title">Название теста</label><input id="import-title" value={preview.title} onChange={e => setPreview({ ...preview, title: e.target.value })} required /><p className="hint">{preview.questions.length} вопросов. Проверь формулировки и правильные ответы.</p>{preview.questions.map((question, index) => <fieldset className="preview-question" key={index}><legend>Вопрос {index + 1}</legend><label htmlFor={`question-${index}`}>Формулировка</label><textarea id={`question-${index}`} value={question.text} required onChange={e => updateQuestion(index, { text: e.target.value })} />{question.options.map((option, oi) => <div className="preview-option" key={oi}><input aria-label={`Правильный вариант ${oi + 1} вопроса ${index + 1}`} type="checkbox" checked={option.is_correct === true} onChange={e => updateQuestion(index, { options: question.options.map((o, i) => ({ ...o, is_correct: i === oi ? e.target.checked : question.question_type === 'single_choice' && e.target.checked ? false : o.is_correct })) })} /><input aria-label={`Текст варианта ${oi + 1} вопроса ${index + 1}`} value={option.text} required onChange={e => updateQuestion(index, { options: question.options.map((o, i) => i === oi ? { ...o, text: e.target.value } : o) })} />{option.is_correct === null && <span title="Правильность неизвестна">?</span>}</div>)}{question.options.some(o => o.is_correct === null) && <button type="button" className="empty-link" onClick={() => updateQuestion(index, { options: question.options.map(o => ({ ...o, is_correct: o.is_correct === true })) })}>Подтвердить отмеченные варианты</button>}{question.question_type === 'text' && <><label htmlFor={`answer-${index}`}>Правильный ответ</label><input id={`answer-${index}`} value={question.correct_answer} required onChange={e => updateQuestion(index, { correct_answer: e.target.value })} /></>}{question.blanks.map((blank, bi) => <div key={bi}><label htmlFor={`blank-${index}-${bi}`}>{blank.prompt || `Пропуск ${bi + 1}`}</label>{blank.choices?.length ? <select id={`blank-${index}-${bi}`} required value={blank.correct_answer} onChange={e => updateQuestion(index, { blanks: question.blanks.map((b, i) => i === bi ? { ...b, correct_answer: e.target.value } : b) })}><option value="">Выбери правильный ответ</option>{blank.choices.map((choice, ci) => <option key={ci}>{choice}</option>)}</select> : <input id={`blank-${index}-${bi}`} value={blank.correct_answer} required onChange={e => updateQuestion(index, { blanks: question.blanks.map((b, i) => i === bi ? { ...b, correct_answer: e.target.value } : b) })} />}</div>)}</fieldset>)}</> : <><label htmlFor="file">PDF или HTML, до 8 МБ</label><input id="file" name="file" type="file" accept=".pdf,.html,.htm" required /></>}{error && <p className="error" role="alert">{error}</p>}<button className="submit" disabled={busy}>{busy ? 'Подождите…' : modal === 'login' ? 'Войти' : modal === 'create' ? 'Создать' : preview ? 'Сохранить тест' : 'Показать превью'}</button></form>{modal === 'login' && <a className="dialog-register" href="/register">Создать аккаунт</a>}</dialog></div>}
  </div>
}
export default HomePage
