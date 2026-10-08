import { describe, expect, it } from 'vitest'
import example from '../../public/quiz-import-example.json'
import { parseJsonText } from './localStore'

describe('JSON import preview', () => {
  it('parses the downloadable example and preserves every supported question type', () => {
    const preview = parseJsonText(JSON.stringify(example), 'fallback')
    expect(preview.title).toBe('Пример импорта: основы HTTP')
    expect(preview.question_count).toBe(5)
    expect(preview.questions.map(question => question.question_type)).toEqual([
      'single_choice', 'multiple_choice', 'text', 'fill_blank', 'matching',
    ])
    expect(preview.needs_review_count).toBe(0)
  })

  it('marks absent answer keys for review instead of guessing', () => {
    const preview = parseJsonText(JSON.stringify({
      title: 'Без ключей',
      questions: [{ text: 'Вопрос', options: ['A', 'B'] }],
    }), 'fallback')
    expect(preview.questions[0].options.map(option => option.is_correct)).toEqual([null, null])
    expect(preview.questions[0].needs_review).toBe(true)
    expect(preview.needs_review_count).toBe(1)
  })

  it('accepts a fenced JSON response from an AI', () => {
    const preview = parseJsonText('```json\n{"title":"Q","questions":[{"text":"Question","question_type":"text","correct_answer":"Answer"}]}\n```', 'fallback')
    expect(preview.title).toBe('Q')
    expect(preview.questions[0].correct_answer).toBe('Answer')
  })

  it('rejects malformed JSON and unsupported question types', () => {
    expect(() => parseJsonText('{broken', 'fallback')).toThrow('Некорректный JSON')
    expect(() => parseJsonText(JSON.stringify({ questions: [{ text: 'Q', question_type: 'essay' }] }), 'fallback')).toThrow('неизвестный question_type')
  })
})
