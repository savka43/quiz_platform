from fastapi import APIRouter

from .attempt_answers.views import router as attempt_answers_router
from .attempts.views import router as attempts_router
from .auth.views import router as auth_router
from .questions.views import router as questions_router
from .tests.views import router as tests_router
from .users.views import router as users_router

router = APIRouter()

router.include_router(router=users_router, prefix="/users")
router.include_router(router=tests_router, prefix="/tests")
router.include_router(router=questions_router, prefix="/questions")
router.include_router(router=attempts_router, prefix="/attempts")
router.include_router(router=attempt_answers_router, prefix="/attempt-answers")
router.include_router(router=auth_router, prefix="/auth")
