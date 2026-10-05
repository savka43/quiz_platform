import { expect, it } from 'vitest'
import { answerBody, answerError, emptyAnswer, sameAnswer } from './answers'
import type { PracticeQuestion } from './answers'

const base: PracticeQuestion = { attempt_question_id: 101, question_id: 5, text: 'Q', question_type: 'single_choice', options: [{ id: 7, text: 'A' }, { id: 9, text: 'B' }], blanks: [] }
it('targets the immutable snapshot, not the deleted or changed source', () => {
  expect(answerBody({ ...base, question_id: null }, { ...emptyAnswer(base), selected_option_ids: [9] })).toEqual({ attempt_question_id: 101, selected_option_ids: [9] })
})
it('requires exactly one valid option for single choice', () => {
  for (const ids of [[], [7, 9], [999], [7, 7]]) expect(answerError(base, { ...emptyAnswer(base), selected_option_ids: ids })).not.toBeNull()
  expect(answerError(base, { ...emptyAnswer(base), selected_option_ids: [9] })).toBeNull()
})
it('accepts multiple selections and ignores selection order when checking saved state', () => {
  const q = { ...base, question_type: 'multiple_choice' as const }
  const answer = { ...emptyAnswer(q), selected_option_ids: [9, 7] }
  expect(answerError(q, answer)).toBeNull()
  expect(sameAnswer(q, answer, { ...answer, selected_option_ids: [7, 9] })).toBe(true)
})
it('does not treat an unsaved or modified answer as saved', () => {
  const answer = { ...emptyAnswer(base), selected_option_ids: [7] }
  expect(sameAnswer(base, answer)).toBe(false)
  expect(sameAnswer(base, answer, { ...answer, selected_option_ids: [9] })).toBe(false)
})
it('trims text without including fields from other answer types', () => {
  const q = { ...base, question_type: 'text' as const, options: [] }
  const answer = { ...emptyAnswer(q), user_answer: '  Ответ  ' }
  expect(answerBody(q, answer)).toEqual({ attempt_question_id: 101, user_answer: 'Ответ' })
  expect(answerError(q, { ...answer, user_answer: '  ' })).not.toBeNull()
})
it('requires every blank and keeps their order', () => {
  const q = { ...base, question_type: 'fill_blank' as const, options: [], blanks: [{ prompt: 'First', choices: [] }, { prompt: 'Second', choices: [] }] }
  expect(emptyAnswer(q).blank_answers).toEqual(['', ''])
  expect(answerError(q, { ...emptyAnswer(q), blank_answers: ['1', ''] })).not.toBeNull()
  expect(answerBody(q, { ...emptyAnswer(q), blank_answers: ['2', '1'] })).toEqual({ attempt_question_id: 101, blank_answers: ['2', '1'] })
})
it('requires a listed matching value for each row', () => {
  const q = { ...base, question_type: 'matching' as const, options: [], blanks: [{ prompt: 'Code', choices: ['200', '404'] }] }
  expect(answerError(q, { ...emptyAnswer(q), blank_answers: ['500'] })).not.toBeNull()
  expect(answerError(q, { ...emptyAnswer(q), blank_answers: ['404'] })).toBeNull()
})
