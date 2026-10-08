import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { apiFetch } from '../api/client'
import QuestionEditor from '../editor/QuestionEditor'
import { move, newQuestion, payload, toDraft, validate } from '../editor/document'
import type { Draft, TestDocument } from '../editor/document'
import NotFoundPage from './NotFoundPage'

type ImportFormat = 'pdf' | 'html' | 'json'
type ParsedQuestion = { text: string; question_type: Draft['questions'][number]['question_type']; options: { text: string; is_correct: boolean | null }[]; correct_answer: string; blanks: { prompt: string; correct_answer: string; choices?: string[] }[]; explanation: string; warnings?: string[] }
type ParsedDocument = { title: string; description?: string; questions: ParsedQuestion[]; warnings?: string[]; question_count?: number; needs_review_count?: number }

const jsonFormat = `{
  "title": "Название теста",
  "description": "Описание",
  "questions": [
    {
      "text": "Текст вопроса",
      "question_type": "single_choice",
      "options": [
        { "text": "Вариант 1", "is_correct": true },
        { "text": "Вариант 2", "is_correct": false }
      ],
      "correct_answer": "",
      "blanks": [],
      "explanation": "Пояснение"
    }
  ]
}`

const pdfFormat = `1. Текст вопроса
Варианты ответа:
1. Первый вариант
2. Второй вариант
Ответ: Первый вариант
Пояснение: Почему этот ответ правильный.

2. Вопрос с текстовым ответом
Ответ: Текст правильного ответа`

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
  const [importFormat, setImportFormat] = useState<ImportFormat | null>(null)
  const [importBusy, setImportBusy] = useState(false)
  const [importError, setImportError] = useState('')
  const [importInfo, setImportInfo] = useState('')
  const [importInput, setImportInput] = useState<File | null>(null)
  const [importWarnings, setImportWarnings] = useState<string[]>([])
  const [draggingFile, setDraggingFile] = useState(false)
  const [formatHelp, setFormatHelp] = useState(false)
  const [formatTab, setFormatTab] = useState<'json' | 'pdf'>('json')
  const importInputRef = useRef<HTMLInputElement>(null)
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
      const path = testId ? `/tests/${testId}/editor` : importFormat ? `/import/${importFormat}/confirm` : '/tests/document'
      const response = await apiFetch(path, { method: testId ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(document) })
      if (!response.ok) throw new Error(response.status === 403 ? 'Нет доступа к этому тесту.' : response.status === 404 ? 'Тест удалён. Скопируй изменения перед выходом.' : response.status === 422 ? 'Сервер отклонил документ. Проверь вопросы и правильные ответы.' : 'Не удалось сохранить. Изменения остались в редакторе — попробуй снова.')
      const result: TestDocument & { id: number } = await response.json()
      const next = toDraft(result)
      setDraft(next); setBaseline(JSON.stringify(payload(next))); setUndo(null); setSaved(true)
      if (!testId) navigate(`/tests/${result.id}/edit`, { replace: true, state: { created: true } })
    } catch (e) { showErrors([e instanceof TypeError ? 'Нет соединения. Изменения остались в редакторе.' : e instanceof Error ? e.message : 'Не удалось сохранить.']) }
    finally { setBusy(false) }
  }
  async function parseImport() {
    if (!importInput) { setImportError('Выбери файл для импорта.'); return }
    if (importInput.size > 8 * 1024 * 1024) { setImportError('Максимальный размер файла — 8 МБ.'); return }
    const name = importInput.name.toLowerCase()
    const format: ImportFormat | null = name.endsWith('.pdf') ? 'pdf' : name.endsWith('.json') ? 'json' : name.endsWith('.html') || name.endsWith('.htm') ? 'html' : null
    if (!format) { setImportError('Поддерживаются PDF, HTML и JSON файлы.'); return }
    setImportBusy(true); setImportError(''); setImportInfo('')
    const data = new FormData()
    data.append('file', importInput)
    try {
      const response = await apiFetch(`/import/${format}/preview`, { method: 'POST', body: data })
      if (!response.ok) {
        const failure = await response.json().catch(() => ({})) as { detail?: string }
        throw new Error(failure.detail || (response.status === 422 ? 'Не удалось распознать вопросы в этом файле.' : 'Не удалось разобрать файл.'))
      }
      const parsed: ParsedDocument = await response.json()
      if (!parsed.questions?.length) throw new Error('В файле не найдено вопросов.')
      const document: TestDocument = {
        title: parsed.title,
        description: parsed.description ?? '',
        questions: parsed.questions.map(question => ({
          text: question.text,
          question_type: question.question_type,
          options: question.options.map(option => ({ text: option.text, is_correct: option.is_correct === true })),
          correct_answer: question.correct_answer,
          blanks: question.blanks.map(blank => ({ prompt: blank.prompt, correct_answer: blank.correct_answer, choices: blank.choices ?? [] })),
          explanation: question.explanation,
        })),
      }
      const warnings = [...(parsed.warnings ?? []), ...parsed.questions.flatMap((question, index) => (question.warnings ?? []).map(warning => `Вопрос ${index + 1}: ${warning}`))]
      setDraft(toDraft(document)); setImportFormat(format); setImportWarnings(warnings); setErrors([]); setSaved(false)
      setImportInfo(`Распознано вопросов: ${parsed.question_count ?? parsed.questions.length}. Требуют проверки: ${parsed.needs_review_count ?? warnings.length}. Проверь и при необходимости исправь их ниже.`)
    } catch (e) { setImportError(e instanceof Error ? e.message : 'Не удалось разобрать файл.') }
    finally { setImportBusy(false) }
  }
  return <main className="editor-page"><Link className="policy-back" to="/" onClick={e => { if (busy || (dirty && !window.confirm('Выйти без сохранения изменений?'))) e.preventDefault() }}>← Мои тесты</Link>
    {loading ? <p role="status">Загружаем тест…</p> : loadError ? <section className="editor-question"><p role="alert">{loadError}</p><button className="secondary-action" onClick={() => setRetry(v => v + 1)}>Повторить</button></section> : <form onSubmit={save} noValidate>
      <div className="editor-heading"><div><p className="home-kicker">{testId ? 'РЕДАКТОР' : 'НОВЫЙ ТЕСТ'}</p><h1>{testId ? 'Редактирование теста' : 'Создать тест'}</h1></div></div>
      {!testId && <section className="editor-import">
        <div className="editor-import-heading"><div><strong>Импортировать тест</strong><p className="hint">Перетащи файл сюда или выбери его на компьютере. PDF, HTML и JSON до 8 МБ.</p></div><button type="button" className="format-help-toggle" aria-expanded={formatHelp} onClick={() => setFormatHelp(value => !value)}>{formatHelp ? 'Скрыть примеры' : 'Примеры форматов файлов'}</button></div>
        <div className={`editor-dropzone${draggingFile ? ' is-dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDraggingFile(true) }} onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDraggingFile(false) }} onDrop={e => { e.preventDefault(); setDraggingFile(false); const file = e.dataTransfer.files[0]; if (file) { setImportInput(file); setImportError('') } }}>
          <span className="dropzone-icon" aria-hidden="true">↑</span><div className="dropzone-copy"><strong>{importInput ? importInput.name : draggingFile ? 'Отпусти файл, чтобы добавить его' : 'Перетащи файл в эту область'}</strong><span>{importInput ? `${(importInput.size / 1024 / 1024).toFixed(2)} МБ` : 'или выбери его через проводник'}</span></div><input ref={importInputRef} className="visually-hidden-file" type="file" accept=".pdf,.html,.htm,.json,application/json" onChange={e => { setImportInput(e.target.files?.[0] ?? null); setImportError('') }} /><button type="button" className="secondary-action" onClick={() => importInputRef.current?.click()}>Выбрать файл</button>
        </div>
        <div className="editor-import-actions"><button type="button" className="primary-action" disabled={importBusy || !importInput} onClick={() => void parseImport()}>{importBusy ? 'Разбираем файл…' : 'Импортировать и проверить'}</button>{importInput && <button type="button" className="import-clear" onClick={() => { setImportInput(null); if (importInputRef.current) importInputRef.current.value = ''; setImportError('') }}>Убрать файл</button>}</div>
        {formatHelp && <div className="format-help-panel"><div className="format-help-tabs" role="tablist" aria-label="Формат исходного файла"><button type="button" role="tab" aria-selected={formatTab === 'json'} className={formatTab === 'json' ? 'active' : ''} onClick={() => setFormatTab('json')}>JSON</button><button type="button" role="tab" aria-selected={formatTab === 'pdf'} className={formatTab === 'pdf' ? 'active' : ''} onClick={() => setFormatTab('pdf')}>PDF</button></div>{formatTab === 'json' ? <><p>JSON должен содержать название и массив <code>questions</code>. У каждого вопроса укажи <code>text</code>, <code>question_type</code>, варианты с <code>is_correct</code>, а также <code>correct_answer</code>, <code>blanks</code> и <code>explanation</code>. Если правильный вариант неизвестен, укажи <code>null</code> и проверь его после импорта.</p><pre>{jsonFormat}</pre></> : <><p>PDF должен содержать текстовый слой и вопросы в таком порядке. Между вопросами сохраняй нумерацию. Название теста берётся из имени PDF-файла.</p><pre>{pdfFormat}</pre></>}<p className="format-help-links"><a href={`${import.meta.env.BASE_URL}quiz-import-ai-prompt.txt`} download>Скачать инструкцию по подготовке файла</a>{' · '}<a href={`${import.meta.env.BASE_URL}${formatTab === 'json' ? 'quiz-import-example.json' : 'quiz-pdf-text-example.txt'}`} download>Скачать полный пример</a></p></div>}
        {importError && <p className="error" role="alert">{importError}</p>}{importInfo && <div className="editor-import-result" role="status"><p>{importInfo}</p>{importWarnings.map((warning, index) => <p className="hint" key={index}>{warning}</p>)}</div>}
      </section>}
      <div className="editor-status" role="status">{saved ? 'Изменения сохранены' : dirty ? 'Есть несохранённые изменения' : testId ? 'Все изменения сохранены' : 'Добавь название и вопросы'}</div>
      {errors.length > 0 && <div className="error" role="alert" tabIndex={-1} ref={errorRef}><strong>Проверь тест</strong><ul>{errors.map((message, i) => <li key={i}>{message}</li>)}</ul></div>}
      <fieldset className="editor-fields" disabled={busy}>
        <section className="editor-question"><label htmlFor="test-title">Название теста</label><input id="test-title" maxLength={200} value={draft.title} onChange={e => { setUndo(null); change({ ...draft, title: e.target.value }) }} placeholder="Например, основы Python" /><label htmlFor="test-description">Описание <span className="optional">необязательно</span></label><textarea id="test-description" rows={3} maxLength={20000} value={draft.description} onChange={e => { setUndo(null); change({ ...draft, description: e.target.value }) }} /></section>
        <div className="editor-section-heading"><h2>Вопросы <span>{draft.questions.length}</span></h2>{undo && <button type="button" className="empty-link" onClick={() => { change(undo); setUndo(null) }}>Отменить удаление</button>}</div>
        {draft.questions.map((question, index) => <QuestionEditor key={question.key} question={question} index={index} count={draft.questions.length} update={q => { setUndo(null); change({ ...draft, questions: draft.questions.map((old, i) => i === index ? q : old) }) }} reorder={to => { setUndo(null); change({ ...draft, questions: move(draft.questions, index, to) }) }} remove={() => { setUndo(draft); change({ ...draft, questions: draft.questions.filter((_, i) => i !== index) }) }} />)}
        <button type="button" className="editor-add" disabled={draft.questions.length >= 1000} onClick={() => { setUndo(null); change({ ...draft, questions: [...draft.questions, newQuestion()] }) }}>+ Добавить вопрос</button>
      </fieldset>
      <div className="editor-save-bottom"><span>Укажи правильные ответы для каждого вопроса.</span><button className="primary-action" disabled={busy} type="submit">{busy ? 'Сохраняем…' : 'Сохранить тест'}</button></div>
    </form>}
  </main>
}
