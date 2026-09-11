import pytest
from test_practice_integration import headers

pytestmark=pytest.mark.anyio


async def test_health_and_cors(client):
    assert (await client.get('/health')).json()=={'status':'ok'}
    response=await client.options('/api/v1/tests/',headers={
        'Origin':'http://localhost:5173', 'Access-Control-Request-Method':'POST',
        'Access-Control-Request-Headers':'authorization,content-type'})
    assert response.status_code==200
    assert response.headers['access-control-allow-origin']=='http://localhost:5173'
    response=await client.options('/api/v1/tests/',headers={
        'Origin':'https://foreign.example', 'Access-Control-Request-Method':'POST'})
    assert 'access-control-allow-origin' not in response.headers


async def test_import_rejects_oversize_and_wrong_type(client,headers):
    response=await client.post('/api/v1/import/pdf/preview',headers={**headers,'Content-Length':str(9*1024*1024)},content=b'')
    assert response.status_code==413
    response=await client.post('/api/v1/import/pdf/preview',headers=headers,files={'file':('bad.pdf',b'not-pdf','application/pdf')})
    assert response.status_code==422
    response=await client.post('/api/v1/import/html/preview',headers=headers,files={'file':('bad.exe',b'html','text/html')})
    assert response.status_code==415


@pytest.mark.parametrize('data',[{'title':'   '},{'title':None},{'description':None}])
async def test_invalid_test_patch_is_not_a_database_error(client,headers,data):
    created=await client.post('/api/v1/tests/',headers=headers,json={'title':'Good'})
    assert created.status_code==201
    response=await client.patch(f'/api/v1/tests/{created.json()["id"]}',headers=headers,json=data)
    assert response.status_code==422


async def test_import_streaming_limit(client,headers):
    async def chunks():
        yield b'--b\r\nContent-Disposition: form-data; name="file"; filename="test.html"\r\nContent-Type: text/html\r\n\r\n'
        for _ in range(10):
            yield b'x' * (1024*1024)
    response=await client.post('/api/v1/import/html/preview',headers={**headers,'Content-Type':'multipart/form-data; boundary=b'},content=chunks())
    assert response.status_code == 413


async def test_private_list_pagination(client,headers):
    for title in ['first','second','third']:
        assert (await client.post('/api/v1/tests/',headers=headers,json={'title':title})).status_code==201
    rows=(await client.get('/api/v1/tests/?limit=1&offset=1',headers=headers)).json()
    assert len(rows)==1 and rows[0]['title']=='second'
    assert (await client.get('/api/v1/tests/?limit=0',headers=headers)).status_code==422
