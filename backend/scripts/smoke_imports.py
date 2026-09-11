"""HTTP smoke check against a local running API, with cleanup of its own data.

Run from backend/: uv run python scripts/smoke_imports.py --pdf /path/file.pdf --html /path/file.html
Uses PostgreSQL settings from .env solely to remove the temporary test user/data.
"""
import argparse
import asyncio
import json
import secrets
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from sqlalchemy import delete
from core import db_helper
from core.models import Attempt, Test, User
from api_v1.editor.schemas import QuestionInput


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--html', type=Path, required=True)
    args = parser.parse_args()
    if not args.base_url.startswith(('http://127.0.0.1:', 'http://localhost:')):
        raise SystemExit('Smoke script is restricted to the local API')
    email = f'smoke-{uuid4().hex}@example.com'
    password = secrets.token_urlsafe(24)
    report = {}
    uid = None

    async def request(client, method, path, expected=200, **kwargs):
        response = await client.request(method, '/api/v1'+path, **kwargs)
        if response.status_code != expected:
            # Do not include request bodies/passwords/tokens in error messages.
            raise RuntimeError(f'{method} {path}: {response.status_code} {response.text[:400]}')
        return response.json() if response.content else None

    try:
        async with httpx.AsyncClient(base_url=args.base_url, timeout=90) as client:
            user = await request(client,'POST','/auth/register',201,json={'email':email,'password':password})
            uid = user['id']
            tokens = await request(client,'POST','/auth/login',data={'username':email,'password':password})
            client.headers['Authorization']='Bearer '+tokens['access_token']
            assert (await request(client,'GET','/users/me'))['id']==uid
            for format, path in [('pdf',args.pdf),('html',args.html)]:
                preview = await request(client,'POST',f'/import/{format}/preview',
                    files={'file':(path.name,path.read_bytes(),'application/pdf' if format=='pdf' else 'text/html')})
                ready=[]
                for question in preview['questions']:
                    if question['needs_review']:
                        continue
                    data={key:question[key] for key in ['text','question_type','options','correct_answer','blanks','explanation']}
                    ready.append(QuestionInput.model_validate(data).model_dump())
                assert ready, 'No unambiguous questions available for smoke test'
                ready[0]['text'] += ' (проверка редактирования превью)'
                saved = await request(client,'POST',f'/import/{format}/confirm',201,
                    json={'title':'Smoke '+format,'questions':ready})
                attempt = await request(client,'POST',f'/tests/{saved["id"]}/attempts',201)
                aid = attempt['id']
                questions = await request(client,'GET',f'/attempts/{aid}/questions')
                assert len(questions)==len(ready)
                for shown, key in zip(questions, ready):
                    assert 'is_correct' not in str(shown) and 'correct_answer' not in str(shown)
                    body={'attempt_question_id':shown['attempt_question_id']}
                    if key['question_type'] in ['single_choice','multiple_choice']:
                        body['selected_option_ids']=[opt['id'] for opt,original in zip(shown['options'],key['options']) if original['is_correct']]
                    elif key['question_type']=='text':
                        body['user_answer']=key['correct_answer']
                    else:
                        body['blank_answers']=[blank['correct_answer'] for blank in key['blanks']]
                    await request(client,'POST',f'/attempts/{aid}/answers',json=body)
                await request(client,'POST',f'/attempts/{aid}/finish')
                result=await request(client,'GET',f'/attempts/{aid}/result')
                assert result['score']==100
                assert await request(client,'GET',f'/attempts/{aid}/mistakes') == []
                await request(client,'DELETE',f'/tests/{saved["id"]}',204)
                assert (await request(client,'GET',f'/attempts/{aid}/result'))['score']==100
                report[format]={'parsed':preview['question_count'],'needs_review':preview['needs_review_count'],
                                'saved_and_completed':len(ready),'score':result['score']}
            refreshed=await request(client,'POST','/auth/refresh',headers={'Authorization':'Bearer '+tokens['refresh_token']})
            await request(client,'POST','/auth/logout',204,headers={'Authorization':'Bearer '+refreshed['refresh_token']})
    finally:
        async with db_helper.session_factory() as session:
            if uid is not None:
                await session.execute(delete(Attempt).where(Attempt.user_id==uid))
                await session.execute(delete(Test).where(Test.user_id==uid))
                await session.execute(delete(User).where(User.id==uid,User.email==email))
                await session.commit()
        await db_helper.engine.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__=='__main__':
    asyncio.run(main())
