# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from samsarix_analytics import MetricRegistry
from samsarix_analytics.exposition import (
    PROMETHEUS_CONTENT_TYPE,
    make_asgi_app,
    make_wsgi_app,
    start_metrics_server,
)


def _registry() -> MetricRegistry:
    registry = MetricRegistry()
    registry.counter("jobs_total", "Jobs", ("status",)).inc(status="ok")
    return registry


def _call_wsgi(
    *,
    method: str = "GET",
    path: str = "/metrics",
    authorization: str | None = None,
) -> tuple[str, dict[str, str], bytes]:
    captured_status = ""
    captured_headers: dict[str, str] = {}

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        _exc_info: object | None = None,
    ) -> None:
        nonlocal captured_status, captured_headers
        captured_status = status
        captured_headers = dict(headers)

    environ: dict[str, object] = {"REQUEST_METHOD": method, "PATH_INFO": path}
    if authorization is not None:
        environ["HTTP_AUTHORIZATION"] = authorization
    chunks = make_wsgi_app(_registry(), bearer_token="secret")(
        environ,
        start_response,  # type: ignore[arg-type]
    )
    assert isinstance(chunks, Iterable)
    return captured_status, captured_headers, b"".join(chunks)


def test_wsgi_app_serves_metrics_and_http_contract() -> None:
    status, headers, body = _call_wsgi(authorization="Bearer secret")
    assert status == "200 OK"
    assert headers["Content-Type"] == PROMETHEUS_CONTENT_TYPE
    assert headers["Cache-Control"] == "no-store"
    assert headers["Content-Length"] == str(len(body))
    assert b"jobs_total" in body

    status, headers, body = _call_wsgi(method="HEAD", authorization="Bearer secret")
    assert status == "200 OK"
    assert int(headers["Content-Length"]) > 0
    assert body == b""

    status, headers, body = _call_wsgi(method="OPTIONS")
    assert status == "200 OK"
    assert headers["Allow"] == "GET, HEAD, OPTIONS"
    assert body == b""


def test_wsgi_app_rejects_unauthorized_wrong_path_and_method() -> None:
    status, headers, _body = _call_wsgi()
    assert status == "401 Unauthorized"
    assert headers["WWW-Authenticate"] == 'Bearer realm="metrics"'
    assert _call_wsgi(path="/other")[0] == "404 Not Found"
    status, headers, _body = _call_wsgi(method="POST")
    assert status == "405 Method Not Allowed"
    assert headers["Allow"] == "GET, HEAD, OPTIONS"


def test_wsgi_app_validates_configuration() -> None:
    registry = MetricRegistry()
    with pytest.raises(ValueError, match="absolute"):
        make_wsgi_app(registry, path="metrics")
    with pytest.raises(ValueError, match="query"):
        make_wsgi_app(registry, path="/metrics?unsafe=true")
    with pytest.raises(ValueError, match="non-empty"):
        make_wsgi_app(registry, bearer_token="")
    with pytest.raises(ValueError, match="too long"):
        make_wsgi_app(registry, bearer_token="x" * 4097)


def test_asgi_app_serves_metrics_and_rejects_non_http_scope() -> None:
    app = make_asgi_app(_registry(), bearer_token="secret")
    messages: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        messages.append(message)

    asyncio.run(
        app(
            {
                "type": "http",
                "method": "GET",
                "path": "/metrics",
                "headers": [(b"authorization", b"Bearer secret")],
            },
            receive,
            send,
        )
    )
    assert messages[0]["status"] == 200
    assert b"jobs_total" in messages[1]["body"]  # type: ignore[operator]

    with pytest.raises(ValueError, match="only HTTP"):
        asyncio.run(app({"type": "websocket"}, receive, send))


def test_standalone_server_uses_ephemeral_loopback_port_and_stops() -> None:
    with start_metrics_server(_registry(), port=0, bearer_token="secret") as server:
        request = Request(server.url, headers={"Authorization": "Bearer secret"})
        with urlopen(request, timeout=2) as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == PROMETHEUS_CONTENT_TYPE
            assert b"jobs_total" in response.read()

        with pytest.raises(HTTPError) as error:
            urlopen(server.url, timeout=2)
        assert error.value.code == 401

    server.close()


@pytest.mark.parametrize("port", [-1, 65536, True])
def test_standalone_server_validates_port(port: int) -> None:
    with pytest.raises(ValueError, match="port"):
        start_metrics_server(MetricRegistry(), port=port)
