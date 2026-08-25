"""A simple per-IP rate limiter for the public streamable-HTTP deployment.

Not meant to be robust against a determined abuser (no distributed state,
trivially bypassed by rotating source IPs) — its job is just to keep one
misbehaving client from exhausting a free-tier server's request budget by
accident, per docs/design/architecture.md's "public server etiquette"
requirement. Deliberately a plain ASGI middleware, not Starlette's
`BaseHTTPMiddleware`: that class buffers the whole response before
forwarding it, which breaks (or at least fights) streamable-HTTP's chunked/
SSE-style responses. This middleware only ever intercepts *before* the
wrapped app starts responding, so the allowed path is a pure pass-through.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

ASGIApp = Callable[
    [MutableMapping[str, Any], Callable[[], Awaitable[Any]], Callable[[Any], Awaitable[None]]],
    Awaitable[None],
]

_RATE_LIMIT_BODY = b"Rate limit exceeded. Please slow down and try again shortly."


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_requests: int, window_seconds: float) -> None:
        self._app = app
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[Any]],
        send: Callable[[Any], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        client = scope.get("client")
        key = client[0] if client else "__unknown__"
        now = time.monotonic()
        cutoff = now - self._window_seconds

        hits = self._hits.setdefault(key, [])
        while hits and hits[0] < cutoff:
            hits.pop(0)

        if len(hits) >= self._max_requests:
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"text/plain; charset=utf-8"),
                        (b"retry-after", str(int(self._window_seconds)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": _RATE_LIMIT_BODY})
            return

        hits.append(now)
        await self._app(scope, receive, send)
