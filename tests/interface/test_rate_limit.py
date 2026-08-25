"""RateLimitMiddleware: a plain ASGI middleware (not Starlette's
BaseHTTPMiddleware, which is known to buffer/interfere with streaming
responses — a real concern for MCP's streamable-http transport). Tested
directly at the ASGI level with httpx's ASGITransport, no real socket.
"""

from __future__ import annotations

import httpx
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from starrydata_mcp.interface.rate_limit import RateLimitMiddleware


async def _ok(request: object) -> PlainTextResponse:
    return PlainTextResponse("ok")


def _client(
    max_requests: int, window_seconds: float, client_ip: str = "1.2.3.4"
) -> httpx.AsyncClient:
    app = Starlette(routes=[Route("/ping", _ok, methods=["GET"])])
    wrapped = RateLimitMiddleware(app, max_requests=max_requests, window_seconds=window_seconds)
    transport = httpx.ASGITransport(app=wrapped, client=(client_ip, 12345))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_requests_under_the_limit_all_succeed() -> None:
    async with _client(max_requests=3, window_seconds=60) as client:
        for _ in range(3):
            response = await client.get("/ping")
            assert response.status_code == 200


async def test_request_over_the_limit_gets_429() -> None:
    async with _client(max_requests=2, window_seconds=60) as client:
        await client.get("/ping")
        await client.get("/ping")
        response = await client.get("/ping")
        assert response.status_code == 429


async def test_limit_is_tracked_per_client_ip_independently() -> None:
    app = Starlette(routes=[Route("/ping", _ok, methods=["GET"])])
    wrapped = RateLimitMiddleware(app, max_requests=1, window_seconds=60)

    async def hit(ip: str) -> int:
        transport = httpx.ASGITransport(app=wrapped, client=(ip, 12345))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/ping")
            return response.status_code

    assert await hit("1.1.1.1") == 200
    assert await hit("1.1.1.1") == 429  # same IP, second hit within the window
    assert await hit("2.2.2.2") == 200  # different IP, unaffected


async def test_old_hits_age_out_of_the_window() -> None:
    import starrydata_mcp.interface.rate_limit as rate_limit_module

    fake_now = [1000.0]
    original_monotonic = rate_limit_module.time.monotonic
    rate_limit_module.time.monotonic = lambda: fake_now[0]
    try:
        async with _client(max_requests=1, window_seconds=10) as client:
            assert (await client.get("/ping")).status_code == 200
            assert (await client.get("/ping")).status_code == 429
            fake_now[0] += 11  # advance past the window
            assert (await client.get("/ping")).status_code == 200
    finally:
        rate_limit_module.time.monotonic = original_monotonic


async def test_non_http_scope_passes_through_unaffected() -> None:
    # e.g. a lifespan scope — must not be rate-limited or crash.
    calls = []

    async def inner_app(scope, receive, send):
        calls.append(scope["type"])

    wrapped = RateLimitMiddleware(inner_app, max_requests=0, window_seconds=60)
    await wrapped({"type": "lifespan"}, None, None)
    assert calls == ["lifespan"]


async def test_missing_client_info_falls_back_to_a_shared_bucket_not_a_crash() -> None:
    app = Starlette(routes=[Route("/ping", _ok, methods=["GET"])])
    wrapped = RateLimitMiddleware(app, max_requests=5, window_seconds=60)
    transport = httpx.ASGITransport(app=wrapped)  # no client= -> scope["client"] is None
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ping")
        assert response.status_code == 200
