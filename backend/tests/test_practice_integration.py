from uuid import uuid4
import pytest
from core.models import User, Favorite, AttemptQuestion, Question
from sqlalchemy import select, func
from api_v1.auth.utils import encode_jwt

pytestmark = pytest.mark.anyio
P='/api/v1'


@pytest.fixture
async def headers(database):
    u=User(email=f'practice-{uuid4().hex}@example.com',hashed_password='unused',active=True)
    database.add(u)
    await database.commit()
    return {'Authorization':'Bearer '+encode_jwt({'sub':str(u.id),'type':'access'})}


@pytest.fixture
def document():
    return {'title':'Sample','questions':[
        {'text':'Single','question_type':'single_choice','options':[{'text':'A','is_correct':True},{'text':'B','is_correct':False}]},
        {'text':'Multi','question_type':'multiple_choice','options':[{'text':'A','is_correct':True},{'text':'B','is_correct':True},{'text':'C','is_correct':False}]},
        {'text':'Text','correct_answer':'Answer'},
        {'text':'Blanks','question_type':'fill_blank','blanks':[{'prompt':'First','correct_answer':'2'}]},
    ]}


async def create(client, headers, document):
    r=await client.post(P+'/tests/document',headers=headers,json=document)
    assert r.status_code==201, r.text
    return r.json()


async def test_full_practice_and_immutable_history(client,database,headers,document):
    test=await create(client,headers,document)
    r=await client.post(f'{P}/tests/{test["id"]}/attempts',headers=headers)
    assert r.status_code==201,r.text
    aid=r.json()['id']
    questions=(await client.get(f'{P}/attempts/{aid}/questions',headers=headers)).json()
    assert len(questions)==4
    assert 'is_correct' not in str(questions)
    assert 'correct_answer' not in str(questions)
    assert (await client.post(f'{P}/attempts/{aid}/finish',headers=headers)).status_code==409
    assert (await client.get(f'{P}/attempts/{aid}/mistakes',headers=headers)).status_code==409
    payloads=[{'selected_option_ids':[questions[0]['options'][0]['id']]},
              {'selected_option_ids':[questions[1]['options'][0]['id']]}, # subset is wrong
              {'user_answer':'answer'},{'blank_answers':['2']}]
    answer_ids=[]
    for q,payload in zip(questions,payloads):
        r=await client.post(f'{P}/attempts/{aid}/answers',headers=headers,
            json={'attempt_question_id':q['attempt_question_id'],**payload})
        assert r.status_code==200,r.text
        assert r.json()['is_correct'] is None
        answer_ids.append(r.json()['id'])
    # Edits after starting do not change the attempt's answer key.
    document['questions'][0]['options'][0]['is_correct']=False
    document['questions'][0]['options'][1]['is_correct']=True
    for q,source in zip(document['questions'],test['questions']): q['id']=source['id']
    assert (await client.put(f'{P}/tests/{test["id"]}/editor',headers=headers,json=document)).status_code==200
    r=await client.post(f'{P}/attempts/{aid}/finish',headers=headers)
    assert r.status_code==200,r.text
    assert r.json()['score']==75
    assert (await client.post(f'{P}/attempts/{aid}/finish',headers=headers)).status_code==409
    assert (await client.post(f'{P}/attempts/{aid}/answers',headers=headers,json={'attempt_question_id':questions[0]['attempt_question_id'],**payloads[0]})).status_code==409
    assert (await client.delete(f'{P}/attempt-answers/{answer_ids[0]}',headers=headers)).status_code==409
    assert (await client.delete(f'{P}/tests/{test["id"]}',headers=headers)).status_code==204
    result=(await client.get(f'{P}/attempts/{aid}/result',headers=headers)).json()
    assert (result['correct'],result['incorrect'],result['score'])==(3,1,75)
    mistakes=(await client.get(f'{P}/attempts/{aid}/mistakes',headers=headers)).json()
    assert mistakes[0]['text']=='Multi'
    assert len(mistakes[0]['correct_options'])==2
    history=(await client.get(P+'/users/me/attempts',headers=headers)).json()
    assert history[0]['test_id'] is None
    assert history[0]['test_title']=='Sample'


async def test_favorites_are_questions_and_span_tests(client,database,headers,document):
    first=await create(client,headers,document)
    second=await create(client,headers,document)
    ids=[first['questions'][0]['id'],second['questions'][2]['id']]
    for qid in ids:
        for _ in range(2):
            assert (await client.post(f'{P}/questions/{qid}/favorite',headers=headers)).status_code==204
    rows=(await client.get(P+'/users/me/favorites',headers=headers)).json()
    assert {q['id'] for q in rows}==set(ids)
    r=await client.post(P+'/favorites/attempts',headers=headers,json={'question_ids':ids})
    assert r.status_code==201,r.text
    assert r.json()['test_id'] is None
    questions=(await client.get(f'{P}/attempts/{r.json()["id"]}/questions',headers=headers)).json()
    assert [q['question_id'] for q in questions]==ids
    assert (await client.post(P+'/favorites/attempts',headers=headers,json={'question_ids':[first['questions'][1]['id']]})).status_code==403
    for _ in range(2):
        assert (await client.delete(f'{P}/questions/{ids[0]}/favorite',headers=headers)).status_code==204
    assert len((await client.get(P+'/users/me/favorites',headers=headers)).json())==1


async def test_import_preview_does_not_save_and_confirm_validates(client,database,headers,document):
    before=await database.scalar(select(func.count()).select_from(Question))
    html='<div class="overflow-hidden"><h2>Вопрос 1</h2><p>Q</p><div><input type="radio"><label>A</label></div><div><input type="radio"><label>B</label></div></div>'
    r=await client.post(P+'/import/html/preview',headers=headers,files={'file':('test.html',html,'text/html')})
    assert r.status_code==200,r.text
    assert r.json()['needs_review_count']==1
    assert await database.scalar(select(func.count()).select_from(Question))==before
    bad={'title':'Bad','questions':[{'text':'Q','question_type':'single_choice','options':[{'text':'A','is_correct':False},{'text':'B','is_correct':False}]}]}
    assert (await client.post(P+'/import/html/confirm',headers=headers,json=bad)).status_code==422
    r=await client.post(P+'/import/html/confirm',headers=headers,json=document)
    assert r.status_code==201,r.text
    assert r.json()['source']=='html_import'


async def test_author_cannot_spoof_score_or_answer_key(client,headers,document):
    test=await create(client,headers,document)
    attempt=(await client.post(f'{P}/tests/{test["id"]}/attempts',headers=headers)).json()
    aid=attempt['id']
    q=(await client.get(f'{P}/attempts/{aid}/questions',headers=headers)).json()[0]
    base={'attempt_question_id':q['attempt_question_id'],'selected_option_ids':[q['options'][0]['id']]}
    for name,value in [('is_correct',True),('score',100),('user_id',1)]:
        assert (await client.post(f'{P}/attempts/{aid}/answers',headers=headers,json={**base,name:value})).status_code==422


async def test_editor_rejects_foreign_question_and_rolls_back(client,database,headers,document):
    test=await create(client,headers,document)
    other=await create(client,headers,document)
    document['questions'][0]['id']=other['questions'][0]['id']
    r=await client.put(f'{P}/tests/{test["id"]}/editor',headers=headers,json=document)
    assert r.status_code==403
    actual=(await client.get(f'{P}/tests/{test["id"]}/editor',headers=headers)).json()
    assert actual==test


async def test_import_is_atomic_when_database_fails(client,database,headers,document,monkeypatch):
    from api_v1.editor import service
    from fastapi import HTTPException
    from core.models import Test as Quiz
    before = await database.scalar(select(func.count()).select_from(Quiz))
    original = service.apply_question
    counter = 0
    async def fail_second(*args, **kwargs):
        nonlocal counter
        counter += 1
        if counter == 2:
            raise HTTPException(503, 'Injected storage failure')
        return await original(*args, **kwargs)
    monkeypatch.setattr(service, 'apply_question', fail_second)
    response = await client.post(P+'/import/html/confirm',headers=headers,json=document)
    assert response.status_code == 503
    # The production dependency rolls back on close. Roll back this fixture's
    # savepoint to emulate that lifecycle before inspecting persisted rows.
    await database.rollback()
    assert await database.scalar(select(func.count()).select_from(Quiz)) == before


async def test_new_routes_are_private(client,database,headers,document):
    test = await create(client,headers,document)
    attempt=(await client.post(f'{P}/tests/{test["id"]}/attempts',headers=headers)).json()
    other = User(email=f'other-{uuid4().hex}@example.com',hashed_password='unused',active=True)
    database.add(other)
    await database.commit()
    foreign = {'Authorization':'Bearer '+encode_jwt({'sub':str(other.id),'type':'access'})}
    qid = test['questions'][0]['id']
    aid = attempt['id']
    for method, path, data in [
        ('get',f'/tests/{test["id"]}/editor',None),
        ('put',f'/tests/{test["id"]}/editor',document),
        ('post',f'/questions/{qid}/favorite',None),
        ('delete',f'/questions/{qid}/favorite',None),
        ('post',f'/tests/{test["id"]}/attempts',None),
        ('get',f'/attempts/{aid}/questions',None),
        ('get',f'/attempts/{aid}/answers',None),
        ('post',f'/attempts/{aid}/answers',{'question_id':qid,'user_answer':'A'}),
        ('post',f'/attempts/{aid}/finish',None),
        ('get',f'/attempts/{aid}/result',None),
        ('get',f'/attempts/{aid}/mistakes',None),
    ]:
        response = await client.request(method,P+path,headers=foreign,**({'json':data} if data is not None else {}))
        assert response.status_code == 403, (path,response.text)
    for path in ['/users/me/favorites','/users/me/attempts']:
        assert (await client.get(P+path,headers=foreign)).json() == []


async def test_resume_answers_are_scoped_and_hide_correctness(client, headers, document):
    document['questions'].append({'text': 'Matching', 'question_type': 'matching',
        'blanks': [{'prompt': 'Not Found', 'correct_answer': '404', 'choices': ['200', '404']}]})
    test = await create(client, headers, document)
    attempt = (await client.post(f'{P}/tests/{test["id"]}/attempts', headers=headers)).json()
    other = (await client.post(f'{P}/tests/{test["id"]}/attempts', headers=headers)).json()
    aid = attempt['id']
    path = f'{P}/attempts/{aid}/answers'
    assert (await client.get(path)).status_code == 401
    assert (await client.get(path, headers=headers)).json() == []
    questions = (await client.get(f'{P}/attempts/{aid}/questions', headers=headers)).json()
    payloads = [{'selected_option_ids': [questions[0]['options'][0]['id']]},
                {'selected_option_ids': [o['id'] for o in questions[1]['options'][:2]]},
                {'user_answer': 'Answer'}, {'blank_answers': ['2']}, {'blank_answers': ['404']}]
    for q, data in zip(questions, payloads):
        response = await client.post(path, headers=headers, json={'attempt_question_id': q['attempt_question_id'], **data})
        assert response.status_code == 200
    rows = (await client.get(path, headers=headers)).json()
    assert len(rows) == 5 and all(a['is_correct'] is None for a in rows)
    assert rows[2]['user_answer'] == 'Answer'
    assert (await client.get(f'{P}/attempts/{other["id"]}/answers', headers=headers)).json() == []
    # Replacing an answer retains one record and can be restored after a reload.
    await client.post(path, headers=headers, json={'attempt_question_id': questions[2]['attempt_question_id'], 'user_answer': 'wrong'})
    assert len((await client.get(path, headers=headers)).json()) == 5
    assert (await client.post(f'{P}/attempts/{aid}/finish', headers=headers)).status_code == 200
    finished = (await client.get(path, headers=headers)).json()
    assert sum(a['is_correct'] for a in finished) == 4
    result = (await client.get(f'{P}/attempts/{aid}/result', headers=headers)).json()
    assert result['score'] == 80
    assert (await client.post(path, headers=headers, json={
        'attempt_question_id': questions[2]['attempt_question_id'], 'user_answer': 'Answer'})).status_code == 409


async def test_parallel_answers_finish_and_edit_snapshot(document):
    import asyncio
    import os
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from sqlalchemy import delete
    from httpx import ASGITransport, AsyncClient
    from core import settings, db_helper
    from core.models import Test as Quiz, Attempt, AttemptAnswer
    from main import app
    engine = create_async_engine(os.environ.get('TEST_DATABASE_URL',settings.database_url),poolclass=NullPool)
    factory = async_sessionmaker(engine,expire_on_commit=False)
    uid = None
    async def independent_session():
        async with factory() as session:
            yield session
    app.dependency_overrides[db_helper.session_dependency] = independent_session
    try:
        async with factory() as session:
            user=User(email=f'parallel-{uuid4().hex}@example.com',hashed_password='unused',active=True)
            session.add(user)
            await session.commit()
            uid=user.id
        auth={'Authorization':'Bearer '+encode_jwt({'sub':str(uid),'type':'access'})}
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
            doc={'title':'Race','questions':[{'text':'Q','correct_answer':'A'}]}
            test=await create(client,auth,doc)
            attempt=(await client.post(f'{P}/tests/{test["id"]}/attempts',headers=auth)).json()
            aid=attempt['id']
            q=(await client.get(f'{P}/attempts/{aid}/questions',headers=auth)).json()[0]
            body={'attempt_question_id':q['attempt_question_id'],'user_answer':'A'}
            answers=await asyncio.gather(*[client.post(f'{P}/attempts/{aid}/answers',headers=auth,json=body) for _ in range(2)])
            assert [r.status_code for r in answers] == [200,200]
            assert answers[0].json()['id']==answers[1].json()['id']
            finishes=await asyncio.gather(*[client.post(f'{P}/attempts/{aid}/finish',headers=auth) for _ in range(2)])
            assert sorted(r.status_code for r in finishes)==[200,409]
            assert (await client.get(f'{P}/attempts/{aid}/result',headers=auth)).json()['score']==100
            assert (await client.patch(f'{P}/attempt-answers/{answers[0].json()["id"]}',headers=auth,json={'user_answer':'B'})).status_code==409
    finally:
        app.dependency_overrides.clear()
        async with factory() as session:
            if uid is not None:
                await session.execute(delete(Attempt).where(Attempt.user_id==uid))
                await session.execute(delete(Quiz).where(Quiz.user_id==uid))
                await session.execute(delete(User).where(User.id==uid))
                await session.commit()
        await engine.dispose()
