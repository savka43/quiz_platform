from datetime import datetime, timezone
import unicodedata

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Test, Question, Attempt, AttemptQuestion, AttemptAnswer, User
from api_v1.editor.service import test_questions, question_document
from api_v1.editor.schemas import QuestionInput
from api_v1.permissions import owned_test, owned_attempt, lock_test
from .schemas import AnswerInput


def normalized(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def evaluate(payload: dict, answer: AnswerInput) -> bool:
    kind = payload['question_type']
    if kind in ('single_choice', 'multiple_choice'):
        if answer.user_answer or answer.blank_answers:
            raise HTTPException(422, 'Use selected_option_ids for a choice question')
        available = {o['id'] for o in payload['options']}
        chosen = set(answer.selected_option_ids)
        if not chosen or not chosen <= available or (kind == 'single_choice' and len(chosen) != 1):
            raise HTTPException(422, 'Invalid option selection')
        return chosen == {o['id'] for o in payload['options'] if o['is_correct']}
    if answer.selected_option_ids:
        raise HTTPException(422, 'This question does not accept option IDs')
    if kind == 'text':
        if answer.blank_answers or not answer.user_answer.strip():
            raise HTTPException(422, 'Provide user_answer')
        return normalized(answer.user_answer) == normalized(payload['correct_answer'])
    if kind == 'matching' and len(answer.blank_answers) == len(payload['blanks']):
        if any(a not in b.get('choices', []) for a, b in zip(answer.blank_answers, payload['blanks'])):
            raise HTTPException(422, 'Choose a listed value for every matching row')
    if answer.user_answer or len(answer.blank_answers) != len(payload['blanks']):
        raise HTTPException(422, 'Provide one answer for each blank')
    return all(normalized(a) == normalized(b['correct_answer'])
               for a, b in zip(answer.blank_answers, payload['blanks']))


async def locked_attempt(session: AsyncSession, attempt_id: int, user: User) -> Attempt:
    attempt = await session.scalar(select(Attempt).where(Attempt.id == attempt_id)
                                  .with_for_update().execution_options(populate_existing=True))
    if attempt is None:
        raise HTTPException(404, 'Attempt not found')
    if attempt.user_id != user.id:
        raise HTTPException(403, 'Access forbidden')
    return attempt


def require_open(attempt: Attempt):
    if attempt.finished_at is not None:
        raise HTTPException(409, 'Attempt is already finished')


async def create_snapshot_attempt(session: AsyncSession, user: User, questions: list[Question],
                                  test: Test | None = None) -> Attempt:
    if not questions:
        raise HTTPException(422, 'Cannot start an empty test')
    snapshots = []
    for q in questions:
        try:
            QuestionInput.model_validate(question_document(q))
        except ValidationError:
            raise HTTPException(422, f'Question {q.id} is not ready for practice; edit its answers') from None
        snapshots.append(question_document(q, option_ids=True))
    attempt = Attempt(user_id=user.id, test_id=test.id if test else None,
                      test_title=test.title if test else 'Избранные вопросы')
    session.add(attempt)
    await session.flush()
    for i, (q, payload) in enumerate(zip(questions, snapshots)):
        session.add(AttemptQuestion(attempt_id=attempt.id, source_question_id=q.id, position=i, payload=payload))
    await session.commit()
    return attempt


async def start_test(session: AsyncSession, user: User, test_id: int) -> Attempt:
    test = await owned_test(session, test_id, user)
    test = await lock_test(session, test_id)
    return await create_snapshot_attempt(session, user, await test_questions(session, test_id), test)


async def snapshot_rows(session: AsyncSession, attempt_id: int) -> list[AttemptQuestion]:
    return list(await session.scalars(select(AttemptQuestion).where(AttemptQuestion.attempt_id == attempt_id)
                                     .order_by(AttemptQuestion.position)))


def public_snapshot(snapshot: AttemptQuestion) -> dict:
    p = snapshot.payload
    return {'attempt_question_id': snapshot.id, 'question_id': snapshot.source_question_id,
            'position': snapshot.position, 'text': p['text'], 'question_type': p['question_type'],
            'options': [{'id': o['id'], 'text': o['text']} for o in p['options']],
            'blanks': [{'prompt': b['prompt'], 'choices': b.get('choices', [])} for b in p['blanks']]}


async def submit_answer(session: AsyncSession, user: User, attempt_id: int, data: AnswerInput) -> AttemptAnswer:
    attempt = await locked_attempt(session, attempt_id, user)
    require_open(attempt)
    query = select(AttemptQuestion).where(AttemptQuestion.attempt_id == attempt_id)
    query = query.where(AttemptQuestion.id == data.attempt_question_id) if data.attempt_question_id is not None else query.where(AttemptQuestion.source_question_id == data.question_id)
    snapshot = await session.scalar(query)
    if snapshot is None:
        raise HTTPException(422, 'Question is not part of this attempt')
    correct = evaluate(snapshot.payload, data)
    answer = await session.scalar(select(AttemptAnswer).where(AttemptAnswer.attempt_question_id == snapshot.id))
    if answer is None:
        answer = AttemptAnswer(attempt_id=attempt_id, question_id=snapshot.source_question_id,
                               attempt_question_id=snapshot.id, user_answer='', is_correct=False)
        session.add(answer)
    answer.selected_option_ids = data.selected_option_ids
    answer.user_answer = data.user_answer
    answer.blank_answers = data.blank_answers
    answer.is_correct = correct
    await session.commit()
    return answer


def public_answer(answer: AttemptAnswer, finished: bool = False) -> dict:
    return dict(id=answer.id, attempt_id=answer.attempt_id, question_id=answer.question_id,
                attempt_question_id=answer.attempt_question_id, user_answer=answer.user_answer,
                selected_option_ids=answer.selected_option_ids, blank_answers=answer.blank_answers,
                is_correct=answer.is_correct if finished else None)


async def finish(session: AsyncSession, user: User, attempt_id: int) -> Attempt:
    attempt = await locked_attempt(session, attempt_id, user)
    require_open(attempt)
    questions = await snapshot_rows(session, attempt_id)
    answers = {a.attempt_question_id: a for a in await session.scalars(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id))}
    if not questions:
        raise HTTPException(409, 'Attempt has no question snapshots')
    if any(q.id not in answers for q in questions):
        raise HTTPException(409, 'Answer every question before finishing')
    # Recompute from snapshots; no client-provided correctness or score is trusted.
    correct = 0
    for q in questions:
        a = answers[q.id]
        a.is_correct = evaluate(q.payload, AnswerInput(attempt_question_id=q.id,
            selected_option_ids=a.selected_option_ids, user_answer=a.user_answer, blank_answers=a.blank_answers))
        correct += a.is_correct
    attempt.score = round(100 * correct / len(questions), 2)
    attempt.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.commit()
    return attempt


async def result(session: AsyncSession, user: User, attempt_id: int, mistakes: bool = False):
    attempt = await owned_attempt(session, attempt_id, user)
    if attempt.finished_at is None:
        raise HTTPException(409, 'Finish the attempt first')
    questions = await snapshot_rows(session, attempt_id)
    answers = {a.attempt_question_id: a for a in await session.scalars(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id))}
    incorrect = []
    for q in questions:
        answer = answers.get(q.id)
        if answer is None or not answer.is_correct:
            incorrect.append(dict(**public_snapshot(q),
                selected_answer=public_answer(answer, True) if answer else None,
                correct_answer=q.payload['correct_answer'],
                correct_options=[o for o in q.payload['options'] if o['is_correct']],
                correct_blanks=q.payload['blanks'], explanation=q.payload['explanation']))
    if mistakes:
        return incorrect
    return dict(attempt_id=attempt.id, title=attempt.test_title, total=len(questions),
                correct=len(questions)-len(incorrect), incorrect=len(incorrect), score=attempt.score,
                finished_at=attempt.finished_at)
