from starlette.types import ASGIApp, Message, Receive, Scope, Send

JSON_LIMIT = 1024 * 1024
UPLOAD_FILES = 2
UPLOAD_HARD_LIMIT_MB = 100
MULTIPART_LIMIT = UPLOAD_FILES * UPLOAD_HARD_LIMIT_MB * 1024 * 1024 + JSON_LIMIT
TOO_LARGE = b'{"detail":"Requisi\\u00e7\\u00e3o maior que o permitido"}'


def limit_for(scope: Scope) -> int:
    headers = dict(scope.get("headers") or [])
    content_type = headers.get(b"content-type", b"").lower()
    return MULTIPART_LIMIT if content_type.startswith(b"multipart/form-data") else JSON_LIMIT


async def reject(send: Send) -> None:
    await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": TOO_LARGE})


class BodySizeLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        limit = limit_for(scope)
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await reject(send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    return {"type": "http.disconnect"}
            return message

        await self.app(scope, limited_receive, send)
