import type { Answer, PracticeQuestion } from './answers'

export default function AnswerFields({ question: q, answer, onChange }: { question: PracticeQuestion; answer: Answer; onChange: (answer: Answer) => void }) {
  if (q.question_type === 'single_choice' || q.question_type === 'multiple_choice') return <div className="practice-options">
    <p className="hint">{q.question_type === 'single_choice' ? 'Выбери один вариант' : 'Выбери все подходящие варианты'}</p>
    {q.options.map(option => <label className={`practice-option ${answer.selected_option_ids.includes(option.id) ? 'selected' : ''}`} key={option.id}>
      <input type={q.question_type === 'single_choice' ? 'radio' : 'checkbox'} name={`answer-${q.attempt_question_id}`} checked={answer.selected_option_ids.includes(option.id)} onChange={e => onChange({ ...answer, selected_option_ids: q.question_type === 'single_choice' ? [option.id] : e.target.checked ? [...answer.selected_option_ids, option.id] : answer.selected_option_ids.filter(id => id !== option.id) })} />
      <span>{option.text}</span>
    </label>)}
  </div>
  if (q.question_type === 'text') return <><label htmlFor="practice-text">Твой ответ</label><textarea id="practice-text" rows={4} maxLength={20000} value={answer.user_answer} onChange={e => onChange({ ...answer, user_answer: e.target.value })} /></>
  return <div className="practice-blanks">{q.blanks.map((blank, i) => <div key={i}>
    <label htmlFor={`practice-blank-${i}`}>{blank.prompt}</label>
    {q.question_type === 'matching' ? <select id={`practice-blank-${i}`} value={answer.blank_answers[i] ?? ''} onChange={e => onChange({ ...answer, blank_answers: answer.blank_answers.map((value, index) => index === i ? e.target.value : value) })}>
      <option value="">Выбери ответ</option>{blank.choices.map((choice, index) => <option key={index} value={choice}>{choice}</option>)}
    </select> : <input id={`practice-blank-${i}`} maxLength={20000} value={answer.blank_answers[i] ?? ''} onChange={e => onChange({ ...answer, blank_answers: answer.blank_answers.map((value, index) => index === i ? e.target.value : value) })} />}
  </div>)}</div>
}
