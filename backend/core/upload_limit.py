from fastapi import HTTPException
from starlette.responses import JSONResponse


class UploadLimitMiddleware:
    """Bound multipart requests before FastAPI spools the complete upload to disk."""

    def __init__(self, app, prefix: str, max_bytes: int):
        self.app, self.prefix, self.max_bytes = app, prefix, max_bytes

    async def __call__(self, scope, receive, send):
        if (scope['type'] != 'http' or not scope['path'].startswith(self.prefix)
                or not scope['path'].endswith('/preview')):
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await JSONResponse({'detail': 'Invalid Content-Length'}, status_code=400)(scope, receive, send)
        if length > self.max_bytes:
            return await JSONResponse({'detail': 'Import request is too large'}, status_code=413)(scope, receive, send)
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get('body', b''))
            if received > self.max_bytes:
                raise HTTPException(413, 'Import request is too large')
            return message

        await self.app(scope, limited_receive, send)
