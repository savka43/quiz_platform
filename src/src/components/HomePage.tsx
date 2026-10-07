import { apiFetch, LOCAL_MODE, session } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { exportLocalBackup, restoreLocalBackup } from '../data/localStore'
import StartAttempt from '../practice/StartAttempt'
import OpenAttempts from '../practice/OpenAttempts'
import { Link, useNavigate } from 'react-router'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

type ImportQuestion = { text: string; question_type: string; options: { text: string; is_correct: boolean | null }[]; correct_answer: string; blanks: { prompt: string; correct_answer: string; choices?: string[] }[]; explanation: string }
type ImportDocument = { title: string; questions: ImportQuestion[] }
type Quiz = { id: number; title: string; description: string; created_at: string }

function HomePage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [loggingOut, setLoggingOut] = useState(false)
  const [tests, setTests] = useState<Quiz[]>([])
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('newest')
  const [modal, setModal] = useState<'import' | null>(null)
  const [error, setError] = useState('')
  const [backupStatus, setBackupStatus] = useState('')
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [revision, setRevision] = useState(0)
  const [preview, setPreview] = useState<ImportDocument | null>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  useEffect(() => { if (modal) dialogRef.current?.showModal() }, [modal])
  const [format, setFormat] = useState('html')

  function downloadBackup() {
    try {
      const url = URL.createObjectURL(new Blob([exportLocalBackup()], { type: 'application/json' }))
      const link = document.createElement('a'); link.href = url; link.download = `quiz-backup-${new Date().toISOString().slice(0, 10)}.json`; link.click(); URL.revokeObjectURL(url); setBackupStatus('Резервная копия скачана.')
    } catch { setError('Не удалось прочитать локальные данные браузера.') }
  }
  async function loadBackup(event: FormEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (!file) return
    if (!window.confirm('Заменить текущие тесты, попытки и избранное данными из этой копии?')) return
    try { restoreLocalBackup(await file.text()); setRevision(value => value + 1); setError(''); setBackupStatus('Резервная копия восстановлена.') }
    catch (e) { setError(e instanceof Error ? e.message : 'Не удалось восстановить резервную копию.') }
  }
  async function deleteTest(test: Quiz) {
    if (!window.confirm(`Удалить тест «${test.title}»? Старые результаты прохождения сохранятся.`)) return
    setError('')
    try {
      const response = await apiFetch(`/tests/${test.id}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('Не удалось удалить тест.')
      setRevision(value => value + 1)
    } catch (e) { setError(e instanceof Error ? e.message : 'Нет соединения с хранилищем.') }
  }

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setLoading(true)
      setError('')
      try {
        const all: Quiz[] = []
        for (let offset = 0; ; offset += 100) {
          const response = await apiFetch(`/tests/?limit=100&offset=${offset}`, { signal: controller.signal })
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
  }, [revision])

  function open(next: 'create' | 'import') {
    if (next === 'create') { navigate('/tests/new'); return }
    setError(''); setPreview(null); setModal(next)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true); setError('')
    try {
      let path = '/tests/'
      let body: BodyInit
      const headers: Record<string, string> = {}
      {
        if (preview) {
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
      const response = await apiFetch(path, { method: 'POST', headers, body })
      if (!response.ok) {
        const failure = await response.json().catch(() => ({})) as { detail?: string }
        throw new Error(failure.detail || (response.status === 401 ? 'Проверьте email и пароль или войдите заново.' : response.status === 422 ? 'Проверьте данные. У каждого вопроса должны быть указаны правильные ответы.' : 'Не получилось выполнить действие. Попробуйте ещё раз.'))
      }
      const result = await response.json()
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
    <header className="home-header"><Link className="home-logo" to="/">quiz<span>.</span></Link><nav className="home-nav" aria-label="Разделы"><Link to="/history">История</Link><Link to="/favorites">Избранное</Link></nav>{LOCAL_MODE ? <Link className="account-button" to="/login">Войти ↗</Link> : <button className="account-button" disabled={loggingOut} title={user?.email} onClick={async () => { setLoggingOut(true); setError(''); try { await session.logout() } catch { setError('Не удалось выйти. Проверьте соединение и повторите попытку.') } finally { setLoggingOut(false) } }}>{loggingOut ? 'Выходим…' : 'Выйти'}<span aria-hidden="true">↗</span></button>}</header>
    <main className="home-content">
      {LOCAL_MODE && <aside className="local-notice"><span><strong>Локальная версия.</strong> Тесты и результаты хранятся только в этом браузере.{backupStatus && <small className="backup-status" role="status">{backupStatus}</small>}</span><span className="local-backup-actions"><button type="button" onClick={downloadBackup}>Скачать копию</button><label className="backup-restore">Восстановить копию<input type="file" accept="application/json,.json" onChange={event => void loadBackup(event)} /></label><Link to="/register">Аккаунт →</Link></span></aside>}
      <OpenAttempts />
      <div className="home-heading"><div><p className="home-kicker">БИБЛИОТЕКА</p><h1>Мои тесты<span>{tests.length.toString().padStart(2, '0')}</span></h1></div><div className="home-actions"><button className="secondary-action" onClick={() => open('import')}><span aria-hidden="true">↑</span> Импортировать</button><button className="primary-action" onClick={() => open('create')}><span aria-hidden="true">+</span> Создать тест</button></div></div>
      <div className="home-toolbar"><div className="home-search"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" /></svg><input aria-label="Поиск тестов" placeholder="Найти тест" value={query} onChange={e => setQuery(e.target.value)} /></div><select aria-label="Сортировка" value={sort} onChange={e => setSort(e.target.value)}><option value="newest">Сначала новые</option><option value="oldest">Сначала старые</option><option value="title">По названию</option></select></div>
      {error && !modal && <div className="error" role="alert">{error} <button onClick={() => setRevision(v => v + 1)}>Повторить</button></div>}
      {loading ? <div className="home-empty" role="status">Загружаем тесты…</div> : filtered.length ? <div className="quiz-grid">{filtered.map(test => <article className="quiz-card" key={test.id}><div className="quiz-card-top"><span className="quiz-mark" aria-hidden="true">≡</span><span>{new Date(test.created_at).toLocaleDateString('ru-RU')}</span></div><h2><Link to={`/tests/${test.id}/edit`}>{test.title}</Link></h2><p>{test.description || 'Без описания'}</p><StartAttempt testId={test.id} /><Link className="quiz-edit" to={`/tests/${test.id}/edit`}>Редактировать</Link><button className="quiz-delete" onClick={() => void deleteTest(test)}>Удалить тест</button><span className="quiz-private">Личный тест</span></article>)}</div> : <section className="home-empty"><div className="empty-drawing" aria-hidden="true"><div className="paper-back" /><div className="paper-front"><span /><span /><i>✓</i></div></div><h2>{query ? 'Ничего не нашлось' : 'Здесь будут твои тесты'}</h2><p>{query ? 'Попробуй другое название.' : 'Создай первый тест или загрузи готовый файл.'}</p><button className="empty-link" onClick={() => query ? setQuery('') : open('create')}>{query ? 'Сбросить поиск' : 'Создать первый тест'} <span aria-hidden="true">→</span></button></section>}
      <div className="home-bottom"><span><span aria-hidden="true">▣</span> Видно только тебе</span><span>PDF и HTML · до 8 МБ</span></div>
    </main>
    <footer className="home-footer"><span>quiz.</span><Link to="/privacy">Обработка персональных данных</Link></footer>
    {modal && <div className="modal-backdrop" onClick={e => { if (e.target === e.currentTarget && !busy) setModal(null) }}><dialog ref={dialogRef} onCancel={e => { e.preventDefault(); if (!busy) setModal(null) }} className="home-dialog" aria-labelledby="dialog-title" onKeyDown={e => { if (e.key === 'Escape' && !busy) setModal(null) }}><button className="dialog-close" aria-label="Закрыть" disabled={busy} onClick={() => setModal(null)}>×</button><h2 id="dialog-title">{preview ? 'Проверить импорт' : 'Импортировать тест'}</h2><form onSubmit={submit}>{preview ? <><label htmlFor="import-title">Название теста</label><input id="import-title" value={preview.title} onChange={e => setPreview({ ...preview, title: e.target.value })} required /><p className="hint">{preview.questions.length} вопросов. Проверь формулировки и правильные ответы.</p>{preview.questions.map((question, index) => <fieldset className="preview-question" key={index}><legend>Вопрос {index + 1}</legend><label htmlFor={`question-${index}`}>Формулировка</label><textarea id={`question-${index}`} value={question.text} required onChange={e => updateQuestion(index, { text: e.target.value })} />{question.options.map((option, oi) => <div className="preview-option" key={oi}><input aria-label={`Правильный вариант ${oi + 1} вопроса ${index + 1}`} type="checkbox" checked={option.is_correct === true} onChange={e => updateQuestion(index, { options: question.options.map((o, i) => ({ ...o, is_correct: i === oi ? e.target.checked : question.question_type === 'single_choice' && e.target.checked ? false : o.is_correct })) })} /><input aria-label={`Текст варианта ${oi + 1} вопроса ${index + 1}`} value={option.text} required onChange={e => updateQuestion(index, { options: question.options.map((o, i) => i === oi ? { ...o, text: e.target.value } : o) })} />{option.is_correct === null && <span title="Правильность неизвестна">?</span>}</div>)}{question.options.some(o => o.is_correct === null) && <button type="button" className="empty-link" onClick={() => updateQuestion(index, { options: question.options.map(o => ({ ...o, is_correct: o.is_correct === true })) })}>Подтвердить отмеченные варианты</button>}{question.question_type === 'text' && <><label htmlFor={`answer-${index}`}>Правильный ответ</label><input id={`answer-${index}`} value={question.correct_answer} required onChange={e => updateQuestion(index, { correct_answer: e.target.value })} /></>}{question.blanks.map((blank, bi) => <div key={bi}><label htmlFor={`blank-${index}-${bi}`}>{blank.prompt || `Пропуск ${bi + 1}`}</label>{blank.choices?.length ? <select id={`blank-${index}-${bi}`} required value={blank.correct_answer} onChange={e => updateQuestion(index, { blanks: question.blanks.map((b, i) => i === bi ? { ...b, correct_answer: e.target.value } : b) })}><option value="">Выбери правильный ответ</option>{blank.choices.map((choice, ci) => <option key={ci}>{choice}</option>)}</select> : <input id={`blank-${index}-${bi}`} value={blank.correct_answer} required onChange={e => updateQuestion(index, { blanks: question.blanks.map((b, i) => i === bi ? { ...b, correct_answer: e.target.value } : b) })} />}</div>)}</fieldset>)}</> : <><label htmlFor="file">PDF или HTML, до 8 МБ</label><input id="file" name="file" type="file" accept=".pdf,.html,.htm" required /></>}{error && <p className="error" role="alert">{error}</p>}<button className="submit" disabled={busy}>{busy ? 'Подождите…' : preview ? 'Сохранить тест' : 'Показать превью'}</button></form></dialog></div>}
  </div>
}
export default HomePage
