import type { QuestionType } from '../editor/document'

export type Attempt = { id: number; test_id: number | null; test_title: string; started_at: string; finished_at: string | null; score: number | null }
export type PracticeQuestion = {
  attempt_question_id: number; question_id: number | null; text: string; question_type: QuestionType;
  options: { id: number; text: string }[]; blanks: { prompt: string; choices: string[] }[];
}
export type Answer = { selected_option_ids: number[]; user_answer: string; blank_answers: string[] }
export type SavedAnswer = Answer & { attempt_question_id: number }
export type Result = { title: string; total: number; correct: number; incorrect: number; score: number }
export function emptyAnswer(question: PracticeQuestion): Answer {
  return { selected_option_ids: [], user_answer: '', blank_answers: question.blanks.map(() => '') }
}
export function answerBody(question: PracticeQuestion, answer: Answer) {
  const target = { attempt_question_id: question.attempt_question_id }
  if (question.question_type === 'single_choice' || question.question_type === 'multiple_choice') return { ...target, selected_option_ids: [...answer.selected_option_ids].sort((a, b) => a - b) }
  if (question.question_type === 'text') return { ...target, user_answer: answer.user_answer.trim() }
  return { ...target, blank_answers: answer.blank_answers.map(value => value.trim()) }
}
export function answerError(question: PracticeQuestion, answer: Answer): string | null {
  const kind = question.question_type
  if (kind === 'single_choice' || kind === 'multiple_choice') {
    if (!answer.selected_option_ids.length) return 'Выбери ответ.'
    if (kind === 'single_choice' && answer.selected_option_ids.length !== 1) return 'Выбери один вариант.'
    if (new Set(answer.selected_option_ids).size !== answer.selected_option_ids.length || answer.selected_option_ids.some(id => !question.options.some(o => o.id === id))) return 'Проверь выбранные варианты.'
  } else if (kind === 'text') {
    if (!answer.user_answer.trim()) return 'Введи ответ.'
    if (answer.user_answer.length > 20000) return 'Ответ слишком длинный.'
  } else {
    if (answer.blank_answers.length !== question.blanks.length || answer.blank_answers.some(value => !value.trim())) return 'Заполни все поля ответа.'
    if (answer.blank_answers.some(value => value.length > 20000)) return 'Ответ слишком длинный.'
    if (kind === 'matching' && answer.blank_answers.some((value, i) => !question.blanks[i].choices.includes(value))) return 'Выбери ответ для каждой строки.'
  }
  return null
}
export function sameAnswer(question: PracticeQuestion, a: Answer, b?: Answer) {
  return !!b && JSON.stringify(answerBody(question, a)) === JSON.stringify(answerBody(question, b))
}
