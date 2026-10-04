import { describe, expect, it } from 'vitest'
import { changeType, move, newQuestion, payload, toDraft, validate } from './document'
import type { Draft } from './document'
function validDraft(): Draft {
  const q = newQuestion()
  q.text = 'Вопрос'
  q.options[0].text = 'Да'; q.options[1].text = 'Нет'
  return { title: 'Тест', description: '', questions: [q] }
}
describe('editor document', () => {
  it('strips UI keys, keeps question IDs and trims text', () => {
    const draft = validDraft()
    draft.questions[0].id = 42
    draft.title = ' Тест '
    const result = payload(draft)
    expect(result.title).toBe('Тест')
    expect(result.questions[0].id).toBe(42)
    expect(result.questions[0]).not.toHaveProperty('key')
    expect(validate(result)).toEqual([])
  })
  it('keeps IDs associated with questions on reorder and removal', () => {
    const draft = validDraft()
    draft.questions[0].id = 10
    draft.questions.push({ ...draft.questions[0], key: 'second', id: 20 })
    draft.questions = move(draft.questions, 0, 1)
    expect(payload(draft).questions.map(q => q.id)).toEqual([20, 10])
    draft.questions.splice(1, 1)
    expect(payload(draft).questions.map(q => q.id)).toEqual([20])
  })
  it('does not reuse identities for new questions', () => {
    const a = newQuestion(), b = newQuestion()
    expect(a.key).not.toBe(b.key)
    expect(a.id).toBeUndefined()
  })
  it('rejects blank titles, empty tests, empty options and wrong correct counts', () => {
    expect(validate({ title: '', description: '', questions: [] })).toHaveLength(2)
    const draft = validDraft()
    draft.questions[0].options[1].is_correct = true
    expect(validate(payload(draft)).join()).toContain('правильные варианты')
    draft.questions[0].options = [{ text: ' ', is_correct: false }]
    expect(validate(payload(draft))).toHaveLength(3)
  })
  it('converts types without sending incompatible answer fields', () => {
    const draft = validDraft()
    const choice = draft.questions[0]
    const text = changeType(choice, 'text')
    expect(text.options).toEqual([])
    text.correct_answer = 'ответ'
    expect(validate(payload({ ...draft, questions: [text] }))).toEqual([])
    const blanks = changeType(text, 'fill_blank')
    expect(blanks.correct_answer).toBe('')
    blanks.blanks[0] = { prompt: '2+2', correct_answer: '4', choices: [] }
    expect(validate(payload({ ...draft, questions: [blanks] }))).toEqual([])
  })
  it('requires matching answers to belong to their choices', () => {
    const draft = validDraft()
    const q = changeType(draft.questions[0], 'matching')
    q.blanks = [{ prompt: 'Код', correct_answer: '404', choices: ['200', '500'] }]
    expect(validate(payload({ ...draft, questions: [q] })).join()).toContain('выберите правильный вариант')
    q.blanks[0].choices.push(' 404 ')
    expect(validate(payload({ ...draft, questions: [q] }))).toEqual([])
  })
  it('reduces multiple correct choices to one when converting to single choice', () => {
    const q = validDraft().questions[0]
    q.options.forEach(o => { o.is_correct = true })
    expect(changeType(q, 'single_choice').options.filter(o => o.is_correct)).toHaveLength(1)
  })
  it('preserves all five types when loading and saving an existing document', () => {
    const draft = validDraft()
    const text = changeType(draft.questions[0], 'text'); text.correct_answer = 'HTTP'
    const multiple = changeType(draft.questions[0], 'multiple_choice'); multiple.options.forEach(o => { o.is_correct = true })
    const blank = changeType(draft.questions[0], 'fill_blank'); blank.blanks = [{ prompt: '2+2', correct_answer: '4', choices: [] }]
    const matching = changeType(draft.questions[0], 'matching'); matching.blanks = [{ prompt: 'Код', correct_answer: '404', choices: ['200', '404'] }]
    draft.questions.push(text, multiple, blank, matching)
    const original = payload(draft)
    expect(validate(original)).toEqual([])
    expect(payload(toDraft(original))).toEqual(original)
  })
})
