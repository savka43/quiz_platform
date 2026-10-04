import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { apiFetch } from '../api/client'
import QuestionEditor from '../editor/QuestionEditor'
import { move, newQuestion, payload, toDraft, validate } from '../editor/document'
import type { Draft, TestDocument } from '../editor/document'
import NotFoundPage from './NotFoundPage'

export default function TestEditorPage() {
  const { testId } = useParams<{ testId: string }>()
  if (testId && !/^[1-9]\d*$/.test(testId)) return <NotFoundPage />
  return <Editor key={testId ?? 'new'} testId={testId} />
}

function Editor({ testId }: { testId?: string }) {
  const navigate = useNavigate()
  const [draft, setDraft] = useState<Draft>(() => ({ title: '', description: '', questions: [newQuestion()] }))
  const [baseline, setBaseline] = useState(() => JSON.stringify(payload(draft)))
  const [loading, setLoading] = useState(!!testId)
  const [busy, setBusy] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [errors, setErrors] = useState<string[]>([])
  const [saved, setSaved] = useState(false)
  const [retry, setRetry] = useState(0)
  const [undo, setUndo] = useState<Draft | null>(null)
  const errorRef = useRef<HTMLDivElement>(null)
  const dirty = JSON.stringify(payload(draft)) !== baseline

  useEffect(() => {
    if (!testId) return
    const controller = new AbortController()
    async function load() {
      setLoading(true); setLoadError('')
      try {
        const response = await apiFetch(`/tests/${testId}/editor`, { signal: controller.signal })
        if (!response.ok) throw new Error(response.status === 403 ? 'Нет доступа к этому тесту.' : response.status === 404 ? 'Тест не найден.' : 'Не удалось загрузить тест.')
        const document = toDraft(await response.json())
        if (!controller.signal.aborted) { setDraft(document); setBaseline(JSON.stringify(payload(document))) }
      } catch (e) { if (!controller.signal.aborted) setLoadError(e instanceof Error ? e.message : 'Нет соединения с сервером.') }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }
    void load()
    return () => controller.abort()
  }, [testId, retry])
  useEffect(() => {
    if (!dirty) return
    function warn(event: BeforeUnloadEvent) { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  function change(next: Draft) { setDraft(next); setSaved(false); setErrors([]) }
  function showErrors(messages: string[]) { setErrors(messages); requestAnimationFrame(() => errorRef.current?.focus()) }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const document = payload(draft)
    const problems = validate(document)
    if (problems.length) { showErrors(problems); return }
    setBusy(true); setErrors([]); setSaved(false)
    try {
      const response = await apiFetch(testId ? `/tests/${testId}/editor` : '/tests/document', { method: testId ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(document) })
      if (!response.ok) throw new Error(response.status === 403 ? 'Нет доступа к этому тесту.' : response.status === 404 ? 'Тест удалён. Скопируй изменения перед выходом.' : response.status === 422 ? 'Сервер отклонил документ. Проверь вопросы и правильные ответы.' : 'Не удалось сохранить. Изменения остались в редакторе — попробуй снова.')
      const result: TestDocument & { id: number } = await response.json()
      const next = toDraft(result)
      setDraft(next); setBaseline(JSON.stringify(payload(next))); setUndo(null); setSaved(true)
      if (!testId) navigate(`/tests/${result.id}/edit`, { replace: true, state: { created: true } })
    } catch (e) { showErrors([e instanceof TypeError ? 'Нет соединения. Изменения остались в редакторе.' : e instanceof Error ? e.message : 'Не удалось сохранить.']) }
    finally { setBusy(false) }
  }
  return <main className="editor-page"><Link className="policy-back" to="/" onClick={e => { if (busy || (dirty && !window.confirm('Выйти без сохранения изменений?'))) e.preventDefault() }}>← Мои тесты</Link>
    {loading ? <p role="status">Загружаем тест…</p> : loadError ? <section className="editor-question"><p role="alert">{loadError}</p><button className="secondary-action" onClick={() => setRetry(v => v + 1)}>Повторить</button></section> : <form onSubmit={save} noValidate>
      <div className="editor-heading"><div><p className="home-kicker">{testId ? 'РЕДАКТОР' : 'НОВЫЙ ТЕСТ'}</p><h1>{testId ? 'Редактирование теста' : 'Создать тест'}</h1></div><button className="primary-action" disabled={busy} type="submit">{busy ? 'Сохраняем…' : 'Сохранить тест'}</button></div>
      <div className="editor-status" role="status">{saved ? 'Изменения сохранены' : dirty ? 'Есть несохранённые изменения' : testId ? 'Все изменения сохранены' : 'Добавь название и вопросы'}</div>
      {errors.length > 0 && <div className="error" role="alert" tabIndex={-1} ref={errorRef}><strong>Проверь тест</strong><ul>{errors.map((message, i) => <li key={i}>{message}</li>)}</ul></div>}
      <fieldset className="editor-fields" disabled={busy}>
        <section className="editor-question"><label htmlFor="test-title">Название теста</label><input id="test-title" maxLength={200} value={draft.title} onChange={e => { setUndo(null); change({ ...draft, title: e.target.value }) }} placeholder="Например, основы Python" /><label htmlFor="test-description">Описание <span className="optional">необязательно</span></label><textarea id="test-description" rows={3} maxLength={20000} value={draft.description} onChange={e => { setUndo(null); change({ ...draft, description: e.target.value }) }} /></section>
        <div className="editor-section-heading"><h2>Вопросы <span>{draft.questions.length}</span></h2>{undo && <button type="button" className="empty-link" onClick={() => { change(undo); setUndo(null) }}>Отменить удаление</button>}</div>
        {draft.questions.map((question, index) => <QuestionEditor key={question.key} question={question} index={index} count={draft.questions.length} update={q => { setUndo(null); change({ ...draft, questions: draft.questions.map((old, i) => i === index ? q : old) }) }} reorder={to => { setUndo(null); change({ ...draft, questions: move(draft.questions, index, to) }) }} remove={() => { setUndo(draft); change({ ...draft, questions: draft.questions.filter((_, i) => i !== index) }) }} />)}
        <button type="button" className="editor-add" disabled={draft.questions.length >= 1000} onClick={() => { setUndo(null); change({ ...draft, questions: [...draft.questions, newQuestion()] }) }}>+ Добавить вопрос</button>
      </fieldset>
      <div className="editor-save-bottom"><span>Правильные ответы увидишь при разборе попытки.</span><button className="primary-action" disabled={busy} type="submit">{busy ? 'Сохраняем…' : 'Сохранить тест'}</button></div>
    </form>}
  </main>
}
