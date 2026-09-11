from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core import db_helper
from core.models import User, Favorite, Question, Attempt, AttemptAnswer, Test
from api_v1.auth.dependencies import get_current_user
from api_v1.permissions import owned_question, owned_attempt, lock_test
from api_v1.editor.service import question_document
from api_v1.attempts.shemas import AttemptRead
from .schemas import AnswerInput, PracticeStart
from . import service

router = APIRouter(tags=['Practice and favorites'])


@router.post('/questions/{question_id}/favorite', status_code=204)
async def add_favorite(question_id: int, user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(db_helper.session_dependency)):
    await owned_question(session, question_id, user)
    await session.execute(insert(Favorite).values(user_id=user.id, question_id=question_id)
        .on_conflict_do_nothing(index_elements=['user_id', 'question_id']))
    await session.commit()


@router.delete('/questions/{question_id}/favorite', status_code=204)
async def remove_favorite(question_id: int, user: User = Depends(get_current_user),
                          session: AsyncSession = Depends(db_helper.session_dependency)):
    await owned_question(session, question_id, user)
    await session.execute(delete(Favorite).where(Favorite.user_id == user.id, Favorite.question_id == question_id))
    await session.commit()


@router.get('/users/me/favorites')
async def favorites(user: User = Depends(get_current_user),
                    session: AsyncSession = Depends(db_helper.session_dependency),
                    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    questions = await session.scalars(select(Question).join(Favorite, Favorite.question_id == Question.id)
        .join(Test, Test.id == Question.test_id).where(Favorite.user_id == user.id, Test.user_id == user.id)
        .options(selectinload(Question.options)).order_by(Favorite.created_at.desc(), Favorite.id.desc())
        .limit(limit).offset(offset))
    return [dict(**question_document(q), test_id=q.test_id) for q in questions]


@router.post('/favorites/attempts', response_model=AttemptRead, status_code=201)
async def practice_favorites(data: PracticeStart, user: User = Depends(get_current_user),
                             session: AsyncSession = Depends(db_helper.session_dependency)):
    # Consistent lock order avoids deadlocks when favorites span several tests.
    test_ids = list(await session.scalars(select(Question.test_id).join(Favorite, Favorite.question_id == Question.id)
        .join(Test, Test.id == Question.test_id).where(Favorite.user_id == user.id, Test.user_id == user.id,
        Question.id.in_(data.question_ids)).distinct().order_by(Question.test_id)))
    for test_id in test_ids:
        await lock_test(session, test_id)
    rows = list(await session.scalars(select(Question).join(Favorite, Favorite.question_id == Question.id)
        .join(Test, Test.id == Question.test_id).where(Favorite.user_id == user.id, Test.user_id == user.id,
        Question.id.in_(data.question_ids)).options(selectinload(Question.options))))
    by_id = {q.id: q for q in rows}
    if len(by_id) != len(data.question_ids):
        raise HTTPException(403, 'Choose only your favorite questions')
    return await service.create_snapshot_attempt(session, user, [by_id[i] for i in data.question_ids])


@router.post('/tests/{test_id}/attempts', response_model=AttemptRead, status_code=201)
async def start_test(test_id: int, user: User = Depends(get_current_user),
                     session: AsyncSession = Depends(db_helper.session_dependency)):
    return await service.start_test(session, user, test_id)


@router.get('/attempts/{attempt_id}/questions')
async def questions(attempt_id: int, user: User = Depends(get_current_user),
                    session: AsyncSession = Depends(db_helper.session_dependency)):
    await owned_attempt(session, attempt_id, user)
    return [service.public_snapshot(q) for q in await service.snapshot_rows(session, attempt_id)]


@router.post('/attempts/{attempt_id}/answers')
async def answer(attempt_id: int, data: AnswerInput, user: User = Depends(get_current_user),
                 session: AsyncSession = Depends(db_helper.session_dependency)):
    return service.public_answer(await service.submit_answer(session, user, attempt_id, data))


@router.post('/attempts/{attempt_id}/finish', response_model=AttemptRead)
async def finish(attempt_id: int, user: User = Depends(get_current_user),
                 session: AsyncSession = Depends(db_helper.session_dependency)):
    return await service.finish(session, user, attempt_id)


@router.get('/attempts/{attempt_id}/result')
async def result(attempt_id: int, user: User = Depends(get_current_user),
                 session: AsyncSession = Depends(db_helper.session_dependency)):
    return await service.result(session, user, attempt_id)


@router.get('/attempts/{attempt_id}/mistakes')
async def mistakes(attempt_id: int, user: User = Depends(get_current_user),
                   session: AsyncSession = Depends(db_helper.session_dependency)):
    return await service.result(session, user, attempt_id, mistakes=True)


@router.get('/users/me/attempts', response_model=list[AttemptRead])
async def history(user: User = Depends(get_current_user),
                   session: AsyncSession = Depends(db_helper.session_dependency),
                   limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return list(await session.scalars(select(Attempt).where(Attempt.user_id == user.id)
        .order_by(Attempt.started_at.desc(), Attempt.id.desc()).limit(limit).offset(offset)))
