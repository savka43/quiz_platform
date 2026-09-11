from uuid import uuid4

import pytest

from api_v1.auth.utils import encode_jwt
from core.models import User, Test as Quiz, Question, Attempt, AttemptAnswer

pytestmark = pytest.mark.anyio
PREFIX = '/api/v1'
RESOURCES = ['tests', 'questions', 'attempts', 'attempt-answers']


@pytest.fixture
async def accounts(database):
    users = [User(email=f'permission-{uuid4().hex}@example.com', hashed_password='unused', active=True) for _ in range(2)]
    database.add_all(users)
    await database.commit()
    return [(u, {'Authorization': 'Bearer ' + encode_jwt({'sub': str(u.id), 'type': 'access'})}) for u in users]


@pytest.fixture
async def records(database, accounts):
    result = []
    for user, _ in accounts:
        test = Quiz(title='Private test', user_id=user.id)
        database.add(test)
        await database.flush()
        question = Question(test_id=test.id, text='Question', correct_answer='answer')
        attempt = Attempt(test_id=test.id, user_id=user.id)
        database.add_all([question, attempt])
        await database.flush()
        answer = AttemptAnswer(attempt_id=attempt.id, question_id=question.id, user_answer='answer', is_correct=True)
        database.add(answer)
        await database.commit()
        result.append(dict(zip(RESOURCES, [test, question, attempt, answer])))
    return result


@pytest.mark.parametrize('resource', RESOURCES)
@pytest.mark.parametrize('method,suffix', [('get','/'), ('post','/'), ('get','/1'), ('patch','/1'), ('delete','/1')])
async def test_all_resource_routes_require_auth(client, resource, method, suffix):
    response = await client.request(method, f'{PREFIX}/{resource}{suffix}')
    assert response.status_code == 401, response.text


@pytest.mark.parametrize('resource', RESOURCES)
@pytest.mark.parametrize('method', ['get', 'patch', 'delete'])
async def test_foreign_item_denied(client, database, accounts, records, resource, method):
    target = records[1][resource]
    response = await client.request(method, f'{PREFIX}/{resource}/{target.id}', headers=accounts[0][1], **({'json': {}} if method == 'patch' else {}))
    assert response.status_code == 403, response.text
    assert await database.get(type(target), target.id) is target


@pytest.mark.parametrize('resource', RESOURCES)
async def test_lists_and_reads_are_private(client, accounts, records, resource):
    for index in (0, 1):
        headers = accounts[index][1]
        response = await client.get(f'{PREFIX}/{resource}/', headers=headers)
        assert response.status_code == 200
        assert [item['id'] for item in response.json()] == [records[index][resource].id]
        assert (await client.get(f'{PREFIX}/{resource}/{records[index][resource].id}', headers=headers)).status_code == 200


@pytest.mark.parametrize('resource', RESOURCES)
async def test_missing_resource(client, accounts, resource):
    assert (await client.get(f'{PREFIX}/{resource}/2147483647', headers=accounts[0][1])).status_code == 404


async def test_create_chain_and_owner_updates_deletes(client, accounts):
    user, headers = accounts[0]
    async def create(resource, payload):
        response = await client.post(f'{PREFIX}/{resource}/', headers=headers, json=payload)
        assert response.status_code == 201, response.text
        return response.json()
    test = await create('tests', {'title': 'Mine'})
    assert test['user_id'] == user.id
    question = await create('questions', {'test_id': test['id'], 'text': 'Q', 'correct_answer': 'A'})
    attempt = await create('attempts', {'test_id': test['id']})
    assert attempt['user_id'] == user.id
    answer = await create('attempt-answers', {'attempt_id': attempt['id'], 'question_id': question['id'], 'user_answer': 'A'})
    for resource, item, payload in [
        ('tests', test, {'title': 'Updated'}), ('questions', question, {'text': 'Updated'}),
        ('attempt-answers', answer, {'user_answer': 'Updated'}),
    ]:
        response = await client.patch(f'{PREFIX}/{resource}/{item["id"]}', headers=headers, json=payload)
        assert response.status_code == 200, response.text
    assert (await client.patch(f'{PREFIX}/attempts/{attempt["id"]}', headers=headers, json={'finished_at': '2026-09-10T12:00:00'})).status_code == 409
    for resource, item in [('attempt-answers', answer), ('attempts', attempt), ('questions', question), ('tests', test)]:
        assert (await client.delete(f'{PREFIX}/{resource}/{item["id"]}', headers=headers)).status_code == 204


async def test_cannot_supply_or_change_owner(client, accounts, records):
    headers = accounts[0][1]
    for resource, payload in [('tests', {'title': 'Fake'}), ('attempts', {'test_id': records[0]['tests'].id})]:
        for field in ('user_id', 'owner_id'):
            data = {**payload, field: accounts[1][0].id}
            assert (await client.post(f'{PREFIX}/{resource}/', headers=headers, json=data)).status_code == 422
            assert (await client.patch(f'{PREFIX}/{resource}/{records[0][resource].id}', headers=headers, json={field: accounts[1][0].id})).status_code == 422


async def test_cannot_create_under_foreign_parents(client, accounts, records):
    own, foreign = records
    headers = accounts[0][1]
    cases = [
        ('questions', {'test_id': foreign['tests'].id, 'text': 'bad', 'correct_answer': 'bad'}),
        ('attempts', {'test_id': foreign['tests'].id}),
        ('attempt-answers', {'attempt_id': foreign['attempts'].id, 'question_id': foreign['questions'].id, 'user_answer': 'bad'}),
        ('attempt-answers', {'attempt_id': own['attempts'].id, 'question_id': foreign['questions'].id, 'user_answer': 'bad'}),
    ]
    for resource, data in cases:
        response = await client.post(f'{PREFIX}/{resource}/', headers=headers, json=data)
        assert response.status_code == 403, response.text


@pytest.mark.parametrize('resource,field', [('questions','test_id'), ('attempts','test_id'), ('attempt-answers','attempt_id'), ('attempt-answers','question_id')])
async def test_parent_links_cannot_be_reassigned_or_cleared(client, accounts, records, resource, field):
    target = records[0][resource]
    for value in (None, 2147483647):
        response = await client.patch(f'{PREFIX}/{resource}/{target.id}', headers=accounts[0][1], json={field: value})
        assert response.status_code == (422 if resource == 'attempt-answers' else 409), response.text


async def test_question_must_belong_to_attempt_test(client, database, accounts, records):
    test = Quiz(user_id=accounts[0][0].id, title='Another own test')
    database.add(test)
    await database.flush()
    question = Question(test_id=test.id, text='Q', correct_answer='A')
    database.add(question)
    await database.commit()
    response = await client.post(f'{PREFIX}/attempt-answers/', headers=accounts[0][1], json={
        'attempt_id': records[0]['attempts'].id, 'question_id': question.id, 'user_answer': 'A',
    })
    assert response.status_code == 422


async def test_test_owner_cannot_read_other_participants_attempts(client, database, accounts, records):
    attempt = Attempt(user_id=accounts[1][0].id, test_id=records[0]['tests'].id)
    database.add(attempt)
    await database.flush()
    answer = AttemptAnswer(attempt_id=attempt.id, question_id=records[0]['questions'].id, user_answer='private', is_correct=False)
    database.add(answer)
    await database.commit()
    for resource, item in [('attempts', attempt), ('attempt-answers', answer)]:
        assert (await client.get(f'{PREFIX}/{resource}/{item.id}', headers=accounts[0][1])).status_code == 403
        response = await client.get(f'{PREFIX}/{resource}/', headers=accounts[0][1])
        assert item.id not in [row['id'] for row in response.json()]
        assert (await client.get(f'{PREFIX}/{resource}/{item.id}', headers=accounts[1][1])).status_code == 200


@pytest.mark.parametrize('resource', RESOURCES)
async def test_resource_rejects_refresh_and_inactive_user(client, database, accounts, resource):
    user, headers = accounts[0]
    refresh = encode_jwt({'sub': str(user.id), 'type': 'refresh'})
    response = await client.get(f'{PREFIX}/{resource}/', headers={'Authorization': 'Bearer ' + refresh})
    assert response.status_code == 401
    user.active = False
    await database.commit()
    assert (await client.get(f'{PREFIX}/{resource}/', headers=headers)).status_code == 403
