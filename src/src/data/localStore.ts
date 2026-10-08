import { validate } from '../editor/document'
import type { QuestionType, TestDocument } from '../editor/document'

const STORAGE_KEY = 'quiz.local.v1'
type LocalOption = { id: number; text: string; is_correct: boolean }
type LocalQuestion = { id: number; text: string; question_type: QuestionType; options: LocalOption[]; correct_answer: string; blanks: { prompt: string; correct_answer: string; choices: string[] }[]; explanation: string }
type LocalTest = { id: number; title: string; description: string; created_at: string; updated_at: string; user_id: number; source: string; questions: LocalQuestion[] }
type Snapshot = { attempt_question_id: number; question_id: number | null; position: number; text: string; question_type: QuestionType; options: LocalOption[]; blanks: LocalQuestion['blanks']; correct_answer: string; explanation: string }
type LocalAnswer = { id: number; attempt_id: number; question_id: number | null; attempt_question_id: number; selected_option_ids: number[]; user_answer: string; blank_answers: string[]; is_correct: boolean | null }
type LocalAttempt = { id: number; user_id: number; test_id: number | null; test_title: string; started_at: string; finished_at: string | null; score: number | null; snapshots: Snapshot[]; answers: LocalAnswer[] }
type Database = { schema: 1; counters: { test: number; question: number; option: number; attempt: number; snapshot: number; answer: number }; tests: LocalTest[]; attempts: LocalAttempt[]; favorites: number[] }

function emptyDatabase(): Database {
  return { schema: 1, counters: { test: 0, question: 0, option: 0, attempt: 0, snapshot: 0, answer: 0 }, tests: [], attempts: [], favorites: [] }
}
export function exportLocalBackup() {
  return window.localStorage.getItem(STORAGE_KEY) ?? JSON.stringify(emptyDatabase(), null, 2)
}
export function restoreLocalBackup(raw: string) {
  const parsed: unknown = JSON.parse(raw)
  if (!parsed || typeof parsed !== 'object' || !('schema' in parsed) || parsed.schema !== 1 || !('tests' in parsed) || !Array.isArray(parsed.tests) || !('attempts' in parsed) || !Array.isArray(parsed.attempts) || !('favorites' in parsed) || !Array.isArray(parsed.favorites) || !('counters' in parsed) || !parsed.counters || typeof parsed.counters !== 'object') {
    throw new Error('Этот файл не похож на резервную копию Quiz.')
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed))
}
function database(): Database {
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) return emptyDatabase()
  const parsed: unknown = JSON.parse(raw)
  if (!parsed || typeof parsed !== 'object' || !('schema' in parsed) || parsed.schema !== 1 || !('tests' in parsed) || !Array.isArray(parsed.tests) || !('attempts' in parsed) || !Array.isArray(parsed.attempts) || !('favorites' in parsed) || !Array.isArray(parsed.favorites) || !('counters' in parsed)) {
    throw new Error('Локальные данные повреждены или созданы другой версией приложения. Экспортируй резервную копию, если она есть.')
  }
  return parsed as Database
}
function save(db: Database) { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(db)) }
function next(db: Database, key: keyof Database['counters']) { db.counters[key] += 1; return db.counters[key] }
function response(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}
function failure(message: string, status = 400) { return response({ detail: message }, status) }
function attemptRead(a: LocalAttempt) { return { id: a.id, user_id: 0, test_id: a.test_id, test_title: a.test_title, started_at: a.started_at, finished_at: a.finished_at, score: a.score } }
function optionRead(o: LocalOption) { return { id: o.id, text: o.text } }
function snapshotRead(q: Snapshot) { return { attempt_question_id: q.attempt_question_id, question_id: q.question_id, position: q.position, text: q.text, question_type: q.question_type, options: q.options.map(optionRead), blanks: q.blanks.map(b => ({ prompt: b.prompt, choices: b.choices })) } }
function answerRead(a: LocalAnswer, finished: boolean) { return { id: a.id, attempt_id: a.attempt_id, question_id: a.question_id, attempt_question_id: a.attempt_question_id, selected_option_ids: a.selected_option_ids, user_answer: a.user_answer, blank_answers: a.blank_answers, is_correct: finished ? a.is_correct : null } }
function normalize(s: string) { return s.normalize('NFKC').trim().replace(/\s+/g, ' ').toLocaleLowerCase() }
function htmlText(element: Element | null | undefined) {
  if (!element) return ''
  const copy = element.cloneNode(true) as HTMLElement
  copy.querySelectorAll('script,style,svg').forEach(node => node.remove())
  copy.querySelectorAll('mjx-container').forEach(container => {
    const math = container.querySelector('math')
    if (math) container.replaceWith(math.cloneNode(true))
  })
  return (copy.textContent ?? '').replace(/\s+/g, ' ').trim()
}
function checkAnswer(q: Snapshot, answer: Pick<LocalAnswer, 'selected_option_ids' | 'user_answer' | 'blank_answers'>) {
  if (q.question_type === 'single_choice' || q.question_type === 'multiple_choice') {
    const valid = new Set(q.options.map(o => o.id)); const selected = new Set(answer.selected_option_ids)
    if (!selected.size || [...selected].some(id => !valid.has(id)) || (q.question_type === 'single_choice' && selected.size !== 1)) throw new Error('Проверь выбранный вариант ответа.')
    return selected.size === q.options.filter(o => o.is_correct).length && q.options.filter(o => o.is_correct).every(o => selected.has(o.id))
  }
  if (q.question_type === 'text') {
    if (!answer.user_answer.trim()) throw new Error('Введи ответ.')
    return normalize(answer.user_answer) === normalize(q.correct_answer)
  }
  if (answer.blank_answers.length !== q.blanks.length || answer.blank_answers.some(v => !v.trim())) throw new Error('Заполни все поля ответа.')
  if (q.question_type === 'matching' && answer.blank_answers.some((v, i) => !q.blanks[i].choices.includes(v))) throw new Error('Выбери вариант для каждой строки.')
  return answer.blank_answers.every((v, i) => normalize(v) === normalize(q.blanks[i].correct_answer))
}
function createAttempt(db: Database, title: string, testId: number | null, questions: LocalQuestion[]) {
  const id = next(db, 'attempt')
  const snapshots = questions.map((q, position) => ({ attempt_question_id: next(db, 'snapshot'), question_id: q.id, position, text: q.text, question_type: q.question_type, options: q.options.map(o => ({ ...o })), blanks: structuredClone(q.blanks), correct_answer: q.correct_answer, explanation: q.explanation }))
  const attempt: LocalAttempt = { id, user_id: 0, test_id: testId, test_title: title, started_at: new Date().toISOString(), finished_at: null, score: null, snapshots, answers: [] }
  db.attempts.push(attempt)
  return attempt
}
function resultFor(a: LocalAttempt) {
  const incorrect = a.answers.filter(answer => answer.is_correct !== true).length
  return { attempt_id: a.id, title: a.test_title, total: a.snapshots.length, correct: a.snapshots.length - incorrect, incorrect, score: a.score, finished_at: a.finished_at }
}
function mistakesFor(a: LocalAttempt) {
  return a.snapshots.flatMap(q => {
    const answer = a.answers.find(row => row.attempt_question_id === q.attempt_question_id)
    if (answer?.is_correct) return []
    return [{ ...snapshotRead(q), selected_answer: answer ? answerRead(answer, true) : null, correct_answer: q.correct_answer, correct_options: q.options.filter(o => o.is_correct).map(optionRead), correct_blanks: q.blanks, explanation: q.explanation }]
  })
}
function parseBody(init: RequestInit) {
  if (typeof init.body !== 'string') return {}
  return JSON.parse(init.body) as Record<string, unknown>
}
function previewQuestion(q: Record<string, unknown>, index: number) {
  return { number: index + 1, text: q.text, question_type: q.question_type, options: q.options ?? [], correct_answer: q.correct_answer ?? '', blanks: q.blanks ?? [], explanation: q.explanation ?? '', source_answer: '', warnings: [], needs_review: false, correct_option_count: Array.isArray(q.options) ? q.options.filter((o: { is_correct?: boolean | null }) => o.is_correct === true).length : 0 }
}
function parseHtml(html: string, title: string) {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  const headings = [...doc.querySelectorAll('h2')].filter(h => /^вопрос\s+\d+$/.test(normalize(htmlText(h))))
  if (!headings.length) throw new Error('Не найдены вопросы в формате SyncShare.')
  const pageHeading = [...doc.querySelectorAll('h1')].find(h => normalize(htmlText(h)) === 'просмотр вопросов')
  const pageTitle = htmlText(pageHeading?.parentElement?.querySelector('p'))
  if (pageTitle) title = pageTitle
  const questions = headings.map((heading, index) => {
    const number = Number(htmlText(heading).match(/\d+/)?.[0] ?? index + 1)
    let card: HTMLElement = heading.parentElement ?? doc.body
    while (card.parentElement && !card.className.split(/\s+/).includes('overflow-hidden')) card = card.parentElement
    const body = htmlText(card.querySelector('p'))
    if (!body) throw new Error(`Не найден текст вопроса ${number}.`)
    const fields = [...card.querySelectorAll<HTMLInputElement>('input[type="radio"],input[type="checkbox"]')]
    const options = fields.map(field => {
      let row: HTMLElement = field.parentElement ?? card
      while (row !== card && !row.querySelector('label')) row = row.parentElement ?? card
      return { text: htmlText(row.querySelector('label')), is_correct: null as boolean | null }
    }).filter(o => o.text)
    let question_type: QuestionType = fields.some(f => f.type === 'checkbox') ? 'multiple_choice' : 'single_choice'
    let correct_answer = ''
    let blanks: { prompt: string; correct_answer: string; choices: string[] }[] = []
    const warnings: string[] = []
    const correctness = new Map<string, boolean | null>()
    const answerLabels = new Map<string, string>()
    const conflicts = new Set<string>()
    if (!options.length) {
      const textFields = [...card.querySelectorAll<HTMLInputElement>('input[type="text"]')]
      question_type = textFields.length > 1 ? 'fill_blank' : 'text'
      if (question_type === 'fill_blank') blanks = textFields.map((_, i) => ({ prompt: `Пропуск ${i + 1}`, correct_answer: '', choices: [] }))
      warnings.push('Правильный текстовый ответ нужно заполнить вручную.')
    } else if (options.length < 2) warnings.push('Проверьте количество вариантов ответа.')
    for (const table of card.querySelectorAll('table')) {
      const headers = [...table.querySelectorAll('th')].map(h => normalize(htmlText(h)))
      if (headers.includes('правильность')) {
        const answerCol = Math.max(0, headers.indexOf('ответ')); const correctCol = headers.indexOf('правильность')
        for (const row of table.querySelectorAll('tr')) {
          const cells = [...row.querySelectorAll('td')]
          if (cells.length <= Math.max(answerCol, correctCol)) continue
          const text = htmlText(cells[answerCol])
          const mark = normalize(htmlText(cells[correctCol]))
          const key = normalize(text)
          if (text && !answerLabels.has(key)) answerLabels.set(key, text)
          const value = mark === 'правильно' ? true : mark === 'неправильно' ? false : null
          const previous = correctness.get(key)
          if (conflicts.has(key)) continue
          if (previous !== undefined && previous !== null && value !== null && previous !== value) {
            correctness.set(key, null)
            conflicts.add(key)
            warnings.push('В таблице есть противоречивые отметки правильности.')
          } else if (value !== null || !correctness.has(key)) correctness.set(key, value)
        }
      }
      if (headers.slice(0, 2).join('|') === 'левая часть|правая часть') {
        question_type = 'matching'
        const choicesHeading = [...card.querySelectorAll('h3')].find(h => h.textContent?.trim() === 'Варианты правой части')
        const choices = choicesHeading ? [...(choicesHeading.parentElement?.querySelectorAll('li') ?? [])].map(li => htmlText(li).replace(/^•\s*/, '')) : []
        blanks = [...table.querySelectorAll('tr')].flatMap(row => { const cells = [...row.querySelectorAll('td')]; return cells.length === 2 ? [{ prompt: htmlText(cells[0]), correct_answer: '', choices }] : [] })
        warnings.push('Проверьте правильные пары в задании на сопоставление.')
      }
    }
    for (const option of options) option.is_correct = correctness.get(normalize(option.text)) ?? null
    if (question_type === 'single_choice' && options.length && !options.some(option => conflicts.has(normalize(option.text)))) {
      const knownCorrect = options.filter(option => option.is_correct === true).length
      const knownWrong = options.filter(option => option.is_correct === false).length
      const unknown = options.filter(option => option.is_correct === null)
      if (knownCorrect === 1) for (const option of unknown) option.is_correct = false
      else if (knownCorrect === 0 && unknown.length === 1 && knownWrong === options.length - 1) unknown[0].is_correct = true
      const labels = options.map(option => normalize(option.text))
      const duplicates = new Set(labels.filter((label, i) => labels.indexOf(label) !== i))
      if (duplicates.size) {
        for (const option of options) if (duplicates.has(normalize(option.text))) option.is_correct = null
        warnings.push('Варианты с одинаковым текстом нужно проверить вручную.')
      }
    }
    if (options.some(o => o.is_correct === null)) warnings.push('В файле нет подтверждённых правильных ответов для всех вариантов.')
    if (card.querySelector('img')) warnings.push('Вопрос содержит изображение; оно не будет добавлено в локальную копию.')
    const explicitAnswer = htmlText([...card.querySelectorAll('h3')].find(h => htmlText(h) === 'Правильный ответ')?.parentElement?.querySelector('p'))
    const tableAnswer = [...correctness].filter(([, value]) => value === true).map(([answer]) => answerLabels.get(answer) ?? answer)
    const textKey = explicitAnswer && explicitAnswer !== 'Правильного ответа нет' ? explicitAnswer : tableAnswer.length === 1 ? tableAnswer[0] : ''
    if (!options.length && question_type === 'text' && textKey) { correct_answer = textKey; warnings.splice(0, warnings.length, ...warnings.filter(w => !w.includes('текстовый ответ'))); }
    return { ...previewQuestion({ text: body, question_type, options, correct_answer, blanks, explanation: '' }, index), number, warnings, needs_review: warnings.length > 0 }
  })
  const declared = htmlText(doc.body).match(/Вопросов в тесте:\s*(\d+)/)
  const warnings = declared && Number(declared[1]) !== questions.length ? [`В файле заявлено ${declared[1]} вопросов, найдено ${questions.length}.`] : []
  return { title: title || 'Импорт HTML', source: 'html_import', question_count: questions.length, needs_review_count: questions.filter(q => q.needs_review).length, warnings, questions }
}
export function parseJsonText(source: string, filenameTitle: string) {
  const cleaned = source.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')
  let data: unknown
  try { data = JSON.parse(cleaned) }
  catch { throw new Error('Некорректный JSON. Скопируй в файл один JSON-объект без пояснений.') }
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('В JSON ожидается объект с полями title и questions.')
  const root = data as Record<string, unknown>
  const title = typeof root.title === 'string' && root.title.trim() ? root.title.trim() : filenameTitle
  const description = typeof root.description === 'string' ? root.description : ''
  if (title.length > 200 || description.length > 20000) throw new Error('Проверь длину названия и описания.')
  if (!Array.isArray(root.questions) || root.questions.length === 0 || root.questions.length > 1000) throw new Error('В questions должно быть от 1 до 1000 вопросов.')
  const allowedTypes: QuestionType[] = ['single_choice', 'multiple_choice', 'text', 'fill_blank', 'matching']
  const questions = root.questions.map((value, index) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`Вопрос ${index + 1}: ожидается JSON-объект.`)
    const raw = value as Record<string, unknown>
    if (typeof raw.text !== 'string' || !raw.text.trim() || raw.text.length > 20000) throw new Error(`Вопрос ${index + 1}: добавь непустое поле text.`)
    const rawOptions = raw.options ?? raw.answers ?? []
    if (!Array.isArray(rawOptions) || rawOptions.length > 100) throw new Error(`Вопрос ${index + 1}: options должен быть массивом до 100 вариантов.`)
    const options = rawOptions.map((option, oi) => {
      const item = typeof option === 'string' ? { text: option, is_correct: null } : option as Record<string, unknown>
      if (!item || typeof item !== 'object' || typeof item.text !== 'string' || !item.text.trim() || item.text.length > 20000 || (item.is_correct !== undefined && item.is_correct !== null && typeof item.is_correct !== 'boolean')) throw new Error(`Вопрос ${index + 1}, вариант ${oi + 1}: нужны text до 20 000 символов и is_correct (true/false/null).`)
      const key = item.is_correct ?? item.correct ?? null
      if (key !== null && typeof key !== 'boolean') throw new Error(`Вопрос ${index + 1}, вариант ${oi + 1}: correct должен быть true, false или null.`)
      return { text: item.text.trim(), is_correct: key as boolean | null }
    })
    const rawBlanks = raw.blanks ?? []
    if (!Array.isArray(rawBlanks) || rawBlanks.length > 100) throw new Error(`Вопрос ${index + 1}: blanks должен быть массивом до 100 полей.`)
    const blanks = rawBlanks.map((blank, bi) => {
      if (!blank || typeof blank !== 'object' || Array.isArray(blank)) throw new Error(`Вопрос ${index + 1}, поле ${bi + 1}: ожидается объект.`)
      const item = blank as Record<string, unknown>
      if (typeof item.prompt !== 'string' || !item.prompt.trim() || item.prompt.length > 20000 || typeof item.correct_answer !== 'string' || item.correct_answer.length > 20000 || (item.choices !== undefined && (!Array.isArray(item.choices) || item.choices.length > 100 || item.choices.some(c => typeof c !== 'string' || c.length > 20000)))) throw new Error(`Вопрос ${index + 1}, поле ${bi + 1}: проверь prompt, correct_answer и choices.`)
      return { prompt: item.prompt.trim(), correct_answer: item.correct_answer.trim(), choices: (item.choices as string[] | undefined)?.map(c => c.trim()).filter(Boolean) ?? [] }
    })
    const trueAnswers = options.filter(option => option.is_correct === true).length
    const kindValue = raw.question_type ?? raw.type
    const kind = kindValue ?? (options.length ? trueAnswers > 1 ? 'multiple_choice' : 'single_choice' : blanks.length ? 'fill_blank' : 'text')
    if (typeof kind !== 'string' || !allowedTypes.includes(kind as QuestionType)) throw new Error(`Вопрос ${index + 1}: неизвестный question_type.`)
    const correctAnswer = raw.correct_answer ?? ''
    const explanation = raw.explanation ?? ''
    if (typeof correctAnswer !== 'string' || correctAnswer.length > 20000 || typeof explanation !== 'string' || explanation.length > 20000) throw new Error(`Вопрос ${index + 1}: correct_answer и explanation должны быть строками до 20 000 символов.`)
    const warnings = Array.isArray(raw.warnings) ? raw.warnings.filter((w): w is string => typeof w === 'string') : []
    if ((kind === 'single_choice' || kind === 'multiple_choice') && options.some(option => option.is_correct === null)) warnings.push('Правильность некоторых вариантов не указана: проверь их в превью.')
    if ((kind === 'single_choice' || kind === 'multiple_choice') && !options.some(option => option.is_correct === true)) warnings.push('Отметь правильный вариант в превью.')
    if (kind === 'text' && !correctAnswer.trim()) warnings.push('Добавь правильный текстовый ответ в превью.')
    if ((kind === 'fill_blank' || kind === 'matching') && (!blanks.length || blanks.some(blank => !blank.prompt || !blank.correct_answer))) warnings.push('Заполни подпись и правильный ответ для каждого поля.')
    return { number: Number.isInteger(raw.number) && Number(raw.number) > 0 ? Number(raw.number) : index + 1, text: raw.text.trim(), question_type: kind, options, correct_answer: correctAnswer.trim(), blanks, explanation: explanation.trim(), source_answer: typeof raw.source_answer === 'string' ? raw.source_answer : '', warnings, needs_review: warnings.length > 0 || options.some(option => option.is_correct === null) }
  })
  return { title, description, source: 'json_import', question_count: questions.length, needs_review_count: questions.filter(q => q.needs_review).length, warnings: [], questions }
}
function parsePdfText(source: string, title: string) {
  const text = source.replace(/\r/g, '').replace(/\u00ad/g, '').replace(/^PAGE \d+\s*$/gm, '')
  if (!text.trim() || text.length > 2_000_000) throw new Error('PDF пустой, слишком большой или не содержит текст.')
  const first = /^\s*1\.\s+/m.exec(text)
  if (!first) throw new Error('Не найден поддерживаемый формат вопросов PDF.')
  const blocks: { number: number; value: string }[] = []; let start = first.index; let number = 1
  while (true) {
    const answer = /^\s*Ответ\s*:/im.exec(text.slice(start))
    if (!answer) throw new Error(`Не найден раздел «Ответ» у вопроса ${number}.`)
    const after = start + answer.index + answer[0].length
    const nextQuestion = new RegExp(`^\\s*${number + 1}\\.\\s+`, 'm').exec(text.slice(after))
    const end = nextQuestion ? after + nextQuestion.index : text.length
    blocks.push({ number, value: text.slice(start, end) })
    if (!nextQuestion) break
    start = end; number += 1
    if (number > 1000) throw new Error('В PDF слишком много вопросов.')
  }
  const questions = blocks.map(({ number: n, value }, index) => {
    const [body0, answer0] = value.split(/\bОтвет\s*:/i, 2)
    let answer = answer0 ?? ''; let explanation = ''
    if (/Пояснение\s*:/i.test(answer)) [answer, explanation] = answer.split(/Пояснение\s*:/i, 2)
    const optionSplit = body0.split('Варианты ответа:')
    const body = optionSplit[0].replace(/^\s*\d+\.\s*/, '').trim()
    const options = optionSplit.length > 1 ? optionSplit[1].split(/^\s*\d+\.\s+/m).slice(1).map(text => text.trim()).filter(Boolean).map(text => ({ text, is_correct: null as boolean | null })) : []
    const answerText = answer.trim().replace(/\s+/g, ' ')
    const correctParts = answerText.split(';').map(v => v.trim()).filter(Boolean)
    const warnings: string[] = []
    for (const part of correctParts) {
      const matches = options.filter(o => normalize(o.text).replace(/[.;]+$/, '') === normalize(part).replace(/[.;]+$/, ''))
      if (matches.length === 1) matches[0].is_correct = true
      else warnings.push(`Не удалось однозначно найти правильный вариант: ${part}`)
    }
    if (!correctParts.length) warnings.push('В файле не указан правильный ответ.')
    if (options.length) for (const option of options) if (option.is_correct === null) option.is_correct = warnings.length ? null : false
    let correct_answer = options.length ? '' : answerText
    let blanks: { prompt: string; correct_answer: string; choices: string[] }[] = []
    let question_type: QuestionType = options.length ? (correctParts.length > 1 || answerText.includes(';') ? 'multiple_choice' : 'single_choice') : 'text'
    if (!options.length && body.toLocaleLowerCase().includes('[пропуск]')) {
      const parsedBlanks = correctParts.flatMap(part => {
        const pair = part.split(/\s+[—–-]\s+/, 2)
        return pair.length === 2 ? [{ prompt: pair[0], correct_answer: pair[1].replace(/[.]$/, ''), choices: [] }] : []
      })
      if (parsedBlanks.length === (body.match(/\[пропуск\]/gi) ?? []).length) { question_type = 'fill_blank'; blanks = parsedBlanks; correct_answer = '' }
      else warnings.push('Задание с пропусками: проверьте и заполните ответы вручную.')
    }
    if (!options.length && !answerText) warnings.push('Заполните правильный ответ.')
    return { ...previewQuestion({ text: body, question_type, options, correct_answer, blanks, explanation: explanation.trim() }, index), number: n, source_answer: answerText, warnings, needs_review: warnings.length > 0 }
  })
  return { title: title || 'Импорт PDF', source: 'pdf_import', question_count: questions.length, needs_review_count: questions.filter(q => q.needs_review).length, warnings: [], questions }
}
async function previewFile(form: FormData) {
  const file = form.get('file')
  if (!(file instanceof File) || !file.size) throw new Error('Выбери файл для импорта.')
  if (file.size > 8 * 1024 * 1024) throw new Error('Максимальный размер файла — 8 МБ.')
  const title = file.name.replace(/\.(html?|pdf)$/i, '')
  if (/\.json$/i.test(file.name)) return parseJsonText(await file.text(), file.name.replace(/\.json$/i, ''))
  if (/\.html?$/i.test(file.name)) return parseHtml(await file.text(), title)
  if (!/\.pdf$/i.test(file.name) || !(await file.slice(0, 5).text()).startsWith('%PDF-')) throw new Error('Поддерживаются HTML и текстовые PDF.')
  const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs')
  pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/legacy/build/pdf.worker.mjs', import.meta.url).toString()
  const pdf = await pdfjs.getDocument({ data: await file.arrayBuffer() }).promise
  if (pdf.numPages > 500) throw new Error('В PDF слишком много страниц.')
  let text = ''
  for (let pageNo = 1; pageNo <= pdf.numPages; pageNo += 1) {
    const page = await pdf.getPage(pageNo)
    const content = await page.getTextContent()
    const items = content.items.filter((item): item is typeof item & { str: string; transform: number[] } => 'str' in item && 'transform' in item)
    const lines: { y: number; parts: { x: number; value: string }[] }[] = []
    for (const item of [...items].sort((a, b) => b.transform[5] - a.transform[5] || a.transform[4] - b.transform[4])) {
      let line = lines.find(row => Math.abs(row.y - item.transform[5]) < 2)
      if (!line) { line = { y: item.transform[5], parts: [] }; lines.push(line) }
      line.parts.push({ x: item.transform[4], value: item.str })
    }
    text += lines.map(line => line.parts.sort((a, b) => a.x - b.x).map(part => part.value).join(' ')).join('\n') + '\n'
  }
  return parsePdfText(text, title)
}

export async function localApiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  try {
    const url = new URL(path, window.location.origin); const route = url.pathname.replace(/\/$/, '') || '/'; const method = (init.method ?? 'GET').toUpperCase(); const db = database()
    const page = <T,>(rows: T[]) => { const offset = Number(url.searchParams.get('offset') ?? 0); const limit = Number(url.searchParams.get('limit') ?? 100); return rows.slice(offset, offset + limit) }
    if (route === '/tests' && method === 'GET') return response(page([...db.tests].sort((a, b) => b.id - a.id).map(test => ({ id: test.id, title: test.title, description: test.description, created_at: test.created_at, user_id: test.user_id }))))
    if (route === '/tests/document' && method === 'POST') {
      const doc = parseBody(init) as unknown as TestDocument; const problems = validate(doc); if (problems.length) return failure(problems.join(' '), 422)
      const testId = next(db, 'test'); const now = new Date().toISOString()
      const questions = doc.questions.map(q => ({ ...structuredClone(q), id: next(db, 'question'), options: q.options.map(o => ({ ...o, id: next(db, 'option') })) }))
      const test: LocalTest = { id: testId, title: doc.title, description: doc.description, created_at: now, updated_at: now, user_id: 0, source: 'manual', questions }; db.tests.push(test); save(db); return response({ id: test.id, title: test.title, description: test.description, source: test.source, questions: test.questions }, 201)
    }
    const testMatch = route.match(/^\/tests\/(\d+)$/)
    if (testMatch && method === 'DELETE') {
      const testId = Number(testMatch[1]); const index = db.tests.findIndex(t => t.id === testId); if (index < 0) return failure('Test not found', 404)
      const removedIds = new Set(db.tests[index].questions.map(q => q.id)); db.tests.splice(index, 1); db.favorites = db.favorites.filter(id => !removedIds.has(id))
      for (const attempt of db.attempts) { for (const snapshot of attempt.snapshots) if (snapshot.question_id !== null && removedIds.has(snapshot.question_id)) snapshot.question_id = null; for (const answer of attempt.answers) if (answer.question_id !== null && removedIds.has(answer.question_id)) answer.question_id = null }
      save(db); return response(null, 204)
    }
    const editorMatch = route.match(/^\/tests\/(\d+)\/editor$/)
    if (editorMatch) {
      const test = db.tests.find(t => t.id === Number(editorMatch[1])); if (!test) return failure('Test not found', 404)
      if (method === 'GET') return response({ id: test.id, title: test.title, description: test.description, source: test.source, questions: test.questions })
      if (method === 'PUT') {
        const doc = parseBody(init) as unknown as TestDocument; const problems = validate(doc); if (problems.length) return failure(problems.join(' '), 422)
        const existing = new Map(test.questions.map(q => [q.id, q])); const questions: LocalQuestion[] = []
        for (const input of doc.questions) {
          const old = input.id ? existing.get(input.id) : undefined
          if (input.id && !old) return failure('Question does not belong to this test', 403)
          questions.push({ ...structuredClone(input), id: old?.id ?? next(db, 'question'), options: input.options.map((o, index) => ({ ...o, id: old?.options[index]?.id ?? next(db, 'option') })) })
        }
        const removedIds = new Set(test.questions.map(q => q.id).filter(id => !questions.some(q => q.id === id)))
        test.title = doc.title; test.description = doc.description; test.updated_at = new Date().toISOString(); test.questions = questions
        db.favorites = db.favorites.filter(id => !removedIds.has(id))
        for (const attempt of db.attempts) { for (const snapshot of attempt.snapshots) if (snapshot.question_id !== null && removedIds.has(snapshot.question_id)) snapshot.question_id = null; for (const answer of attempt.answers) if (answer.question_id !== null && removedIds.has(answer.question_id)) answer.question_id = null }
        save(db)
        return response({ id: test.id, title: test.title, description: test.description, source: test.source, questions })
      }
    }
    if (route.startsWith('/import/') && route.endsWith('/preview') && method === 'POST') {
      if (!(init.body instanceof FormData)) return failure('Choose a file to import')
      try { return response(await previewFile(init.body)) }
      catch (error) { return failure(error instanceof Error ? error.message : 'Не удалось разобрать файл.', 422) }
    }
    if (route.startsWith('/import/') && route.endsWith('/confirm') && method === 'POST') {
      const preview = parseBody(init); const rawQuestions = Array.isArray(preview.questions) ? preview.questions as Record<string, unknown>[] : []
      const doc = { title: String(preview.title ?? ''), description: String(preview.description ?? ''), questions: rawQuestions.map(q => ({ text: String(q.text ?? ''), question_type: q.question_type as QuestionType, options: (q.options as { text: string; is_correct: boolean | null }[] ?? []).map(o => ({ text: o.text, is_correct: o.is_correct === true })), correct_answer: String(q.correct_answer ?? ''), blanks: q.blanks ?? [], explanation: String(q.explanation ?? '') })) } as TestDocument
      if (rawQuestions.some(q => Array.isArray(q.options) && (q.options as { is_correct: boolean | null }[]).some(o => o.is_correct === null))) return failure('Отметь или сними отметку правильности у каждого варианта.', 422)
      const problems = validate(doc); if (problems.length) return failure(problems.join(' '), 422)
      const testId = next(db, 'test'); const now = new Date().toISOString(); const questions = doc.questions.map(q => ({ ...q, id: next(db, 'question'), options: q.options.map(o => ({ ...o, id: next(db, 'option') })) }))
      const test: LocalTest = { id: testId, title: doc.title, description: '', created_at: now, updated_at: now, user_id: 0, source: String(preview.source ?? 'local_import'), questions }; db.tests.push(test); save(db); return response({ id: test.id, title: test.title, description: test.description, source: test.source, questions }, 201)
    }
    const testAttempt = route.match(/^\/tests\/(\d+)\/attempts$/)
    if (testAttempt && method === 'POST') {
      const test = db.tests.find(t => t.id === Number(testAttempt[1])); if (!test) return failure('Test not found', 404)
      if (!test.questions.length) return failure('Cannot start an empty test', 422)
      const attempt = createAttempt(db, test.title, test.id, test.questions); save(db); return response(attemptRead(attempt), 201)
    }
    if (route === '/favorites/attempts' && method === 'POST') {
      const ids = parseBody(init).question_ids as number[]; if (!Array.isArray(ids) || !ids.length || ids.some((id, i) => ids.indexOf(id) !== i || !db.favorites.includes(id))) return failure('Choose only your favorite questions', 403)
      const questions = ids.map(id => db.tests.flatMap(t => t.questions).find(q => q.id === id)).filter((q): q is LocalQuestion => !!q)
      if (questions.length !== ids.length) return failure('Some favorite questions no longer exist', 403)
      const attempt = createAttempt(db, 'Избранные вопросы', null, questions); save(db); return response(attemptRead(attempt), 201)
    }
    const favoriteMatch = route.match(/^\/questions\/(\d+)\/favorite$/)
    if (favoriteMatch) {
      const questionId = Number(favoriteMatch[1]); const exists = db.tests.some(t => t.questions.some(q => q.id === questionId)); if (!exists) return failure('Question not found', 404)
      if (method === 'POST') { if (!db.favorites.includes(questionId)) db.favorites.push(questionId); save(db); return response(null, 204) }
      if (method === 'DELETE') { db.favorites = db.favorites.filter(id => id !== questionId); save(db); return response(null, 204) }
    }
    if (route === '/users/me/favorites' && method === 'GET') return response(page(db.favorites.flatMap(id => { const test = db.tests.find(t => t.questions.some(q => q.id === id)); const question = test?.questions.find(q => q.id === id); return test && question ? [{ ...question, test_id: test.id }] : [] })))
    if (route === '/users/me/attempts' && method === 'GET') return response(page([...db.attempts].sort((a, b) => b.started_at.localeCompare(a.started_at)).map(attemptRead)))
    const attemptMatch = route.match(/^\/attempts\/(\d+)(?:\/(questions|answers|finish|result|mistakes))?$/)
    if (attemptMatch) {
      const attempt = db.attempts.find(a => a.id === Number(attemptMatch[1])); if (!attempt) return failure('Attempt not found', 404)
      const sub = attemptMatch[2]
      if (!sub && method === 'GET') return response(attemptRead(attempt))
      if (sub === 'questions' && method === 'GET') return response(attempt.snapshots.map(snapshotRead))
      if (sub === 'answers' && method === 'GET') return response(attempt.answers.map(a => answerRead(a, !!attempt.finished_at)))
      if (sub === 'answers' && method === 'POST') {
        if (attempt.finished_at) return failure('Attempt is already finished', 409)
        const input = parseBody(init); const target = Number(input.attempt_question_id); const question = attempt.snapshots.find(q => q.attempt_question_id === target); if (!question) return failure('Question is not part of this attempt', 422)
        const answerInput = { selected_option_ids: (input.selected_option_ids as number[] | undefined) ?? [], user_answer: String(input.user_answer ?? ''), blank_answers: (input.blank_answers as string[] | undefined) ?? [] }
        let correct: boolean; try { correct = checkAnswer(question, answerInput) } catch (e) { return failure(e instanceof Error ? e.message : 'Invalid answer', 422) }
        let answer = attempt.answers.find(a => a.attempt_question_id === target)
        if (!answer) { answer = { id: next(db, 'answer'), attempt_id: attempt.id, question_id: question.question_id, attempt_question_id: target, selected_option_ids: [], user_answer: '', blank_answers: [], is_correct: null }; attempt.answers.push(answer) }
        Object.assign(answer, answerInput, { is_correct: correct }); save(db); return response(answerRead(answer, false))
      }
      if (sub === 'finish' && method === 'POST') {
        if (attempt.finished_at) return failure('Attempt is already finished', 409)
        if (attempt.snapshots.some(q => !attempt.answers.some(a => a.attempt_question_id === q.attempt_question_id))) return failure('Answer every question before finishing', 409)
        for (const answer of attempt.answers) { const q = attempt.snapshots.find(row => row.attempt_question_id === answer.attempt_question_id)!; answer.is_correct = checkAnswer(q, answer) }
        const correct = attempt.answers.filter(a => a.is_correct).length; attempt.score = Math.round(correct / attempt.snapshots.length * 10000) / 100; attempt.finished_at = new Date().toISOString(); save(db); return response(attemptRead(attempt))
      }
      if ((sub === 'result' || sub === 'mistakes') && method === 'GET') {
        if (!attempt.finished_at) return failure('Finish the attempt first', 409)
        return response(sub === 'result' ? resultFor(attempt) : mistakesFor(attempt))
      }
    }
    return failure('Локальный режим: неизвестная операция.', 404)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Ошибка локального хранилища.'
    return failure(message.includes('Quota') || message.includes('quota') ? 'В браузере закончилось место. Удали ненужные данные или экспортируй резервную копию.' : message, 507)
  }
}
