"""Lightweight request correlation without modifying API response bodies."""
from uuid import uuid4

class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = uuid4().hex.encode('ascii')
        async def send_with_id(message):
            if message['type'] == 'http.response.start':
                message = {**message, 'headers': [*message.get('headers', []), (b'x-request-id', request_id)]}
            await send(message)
        await self.app(scope, receive, send_with_id)
