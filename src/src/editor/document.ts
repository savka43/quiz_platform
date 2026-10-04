export type QuestionType = 'single_choice' | 'multiple_choice' | 'text' | 'fill_blank' | 'matching'
export type Option = { text: string; is_correct: boolean }
export type Blank = { prompt: string; correct_answer: string; choices: string[] }
export type Question = { id?: number; text: string; question_type: QuestionType; options: Option[]; correct_answer: string; blanks: Blank[]; explanation: string }
export type TestDocument = { title: string; description: string; questions: Question[] }
export type DraftQuestion = Question & { key: string }
export type Draft = Omit<TestDocument, 'questions'> & { questions: DraftQuestion[] }
export const types: Record<QuestionType, string> = { single_choice: 'Один вариант', multiple_choice: 'Несколько вариантов', text: 'Текстовый ответ', fill_blank: 'Пропуски', matching: 'Сопоставление' }
export function newQuestion(): DraftQuestion {
  return { key: crypto.randomUUID(), text: '', question_type: 'single_choice', options: [{ text: '', is_correct: true }, { text: '', is_correct: false }], correct_answer: '', blanks: [], explanation: '' }
}
export function toDraft(document: TestDocument): Draft {
  return { title: document.title, description: document.description, questions: document.questions.map(q => ({ ...q, key: crypto.randomUUID() })) }
}
export function payload(draft: Draft): TestDocument {
  return { title: draft.title.trim(), description: draft.description.trim(), questions: draft.questions.map(q => ({ ...(q.id ? { id: q.id } : {}), text: q.text.trim(), question_type: q.question_type, explanation: q.explanation.trim(), correct_answer: q.correct_answer.trim(), options: q.options.map(o => ({ text: o.text.trim(), is_correct: o.is_correct })), blanks: q.blanks.map(b => ({ prompt: b.prompt.trim(), correct_answer: b.correct_answer.trim(), choices: b.choices.map(c => c.trim()).filter(Boolean) })) })) }
}
export function changeType(q: DraftQuestion, type: QuestionType): DraftQuestion {
  const choice = type === 'single_choice' || type === 'multiple_choice'
  const options = choice ? (q.options.length ? q.options.map(o => ({ ...o })) : newQuestion().options) : []
  const firstCorrect = Math.max(0, options.findIndex(o => o.is_correct))
  return { ...q, question_type: type, options: type === 'single_choice' ? options.map((o, i) => ({ ...o, is_correct: i === firstCorrect })) : options, correct_answer: type === 'text' ? q.correct_answer : '', blanks: type === 'fill_blank' || type === 'matching' ? (q.blanks.length ? q.blanks.map(b => ({ ...b, choices: [...b.choices] })) : [{ prompt: '', correct_answer: '', choices: [] }]) : [] }
}
export function move<T>(items: T[], from: number, to: number): T[] {
  if (to < 0 || to >= items.length) return items
  const result = [...items]
  const [item] = result.splice(from, 1)
  result.splice(to, 0, item)
  return result
}
export function validate(document: TestDocument): string[] {
  const errors: string[] = []
  if (!document.title || document.title.length > 200) errors.push('Название: от 1 до 200 символов.')
  if (document.description.length > 20000) errors.push('Описание: не больше 20 000 символов.')
  if (!document.questions.length || document.questions.length > 1000) errors.push('В тесте должно быть от 1 до 1000 вопросов.')
  document.questions.forEach((q, i) => {
    const add = (message: string) => errors.push(`Вопрос ${i + 1}: ${message}`)
    if (!q.text || q.text.length > 20000) add('введите текст, не больше 20 000 символов.')
    if (q.explanation.length > 20000) add('пояснение слишком длинное.')
    if (q.question_type === 'single_choice' || q.question_type === 'multiple_choice') {
      if (q.options.length < 2 || q.options.length > 100) add('нужно от 2 до 100 вариантов.')
      if (q.options.some(o => !o.text || o.text.length > 20000)) add('заполните все варианты ответа.')
      const correct = q.options.filter(o => o.is_correct).length
      if (!correct || (q.question_type === 'single_choice' && correct !== 1)) add('отметьте правильные варианты согласно типу вопроса.')
    } else if (q.question_type === 'text') {
      if (!q.correct_answer || q.correct_answer.length > 20000) add('введите правильный ответ, не больше 20 000 символов.')
    } else {
      if (!q.blanks.length || q.blanks.length > 100) add('нужно от 1 до 100 полей ответа.')
      q.blanks.forEach((b, bi) => {
        if (!b.prompt || !b.correct_answer || b.prompt.length > 20000 || b.correct_answer.length > 20000) add(`заполните подпись и ответ для поля ${bi + 1} (до 20 000 символов).`)
        if (b.choices.length > 100 || b.choices.some(c => c.length > 20000)) add(`проверьте варианты поля ${bi + 1}: максимум 100 вариантов по 20 000 символов.`)
        if (q.question_type === 'matching' && !b.choices.includes(b.correct_answer)) add(`выберите правильный вариант для поля ${bi + 1}.`)
      })
    }
  })
  return errors
}
