# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping

import pytest

from samsarix_analytics import HTTPMetrics, MetricRegistry, instrument_asgi, instrument_wsgi
from samsarix_analytics.exposition import ASGIReceive, ASGIScope, ASGISend, StartResponse


def _start_response(
    _status: str,
    _headers: list[tuple[str, str]],
    _exc_info: object | None = None,
) -> None:
    return None


def test_wsgi_middleware_records_stream_completion_and_normalizes_labels() -> None:
    registry = MetricRegistry()
    closed = False

    class Response:
        def __iter__(self) -> Iterable[bytes]:
            yield b"one"
            yield b"two"

        def close(self) -> None:
            nonlocal closed
            closed = True

    def app(_environ: Mapping[str, object], start_response: StartResponse) -> Iterable[bytes]:
        start_response("204 No Content", [])
        return Response()

    wrapped = instrument_wsgi(app, registry)
    assert b"".join(wrapped({"REQUEST_METHOD": "CUSTOM"}, _start_response)) == b"onetwo"
    assert closed
    assert registry.query("http_server_requests_total")[0].labels == {
        "method": "OTHER",
        "status_class": "2xx",
    }
    assert registry.query("http_server_active_requests")[0].value == 0
    assert registry.query("http_server_request_duration_seconds", "count")[0].value == 1


def test_wsgi_middleware_records_failures_and_preserves_exception() -> None:
    registry = MetricRegistry()

    def app(_environ: Mapping[str, object], _start_response: StartResponse) -> Iterable[bytes]:
        raise RuntimeError("application failed")

    with pytest.raises(RuntimeError, match="application failed"):
        instrument_wsgi(app, registry)({"REQUEST_METHOD": "GET"}, _start_response)
    assert registry.query("http_server_requests_total")[0].labels["status_class"] == "5xx"
    assert registry.query("http_server_active_requests")[0].value == 0


def test_wsgi_middleware_finalizes_when_stream_raises() -> None:
    registry = MetricRegistry()

    def app(_environ: Mapping[str, object], start_response: StartResponse) -> Iterable[bytes]:
        start_response("200 OK", [])
        yield b"partial"
        raise RuntimeError("stream failed")

    response = instrument_wsgi(app, registry)({"REQUEST_METHOD": "POST"}, _start_response)
    with pytest.raises(RuntimeError, match="stream failed"):
        list(response)
    assert registry.query("http_server_requests_total")[0].labels == {
        "method": "POST",
        "status_class": "2xx",
    }


def test_http_metrics_registration_is_reusable_and_validated() -> None:
    registry = MetricRegistry()
    first = HTTPMetrics.create(registry)
    second = HTTPMetrics.create(registry)
    assert first.requests is second.requests
    with pytest.raises(ValueError, match="metric names"):
        HTTPMetrics.create(registry, prefix="bad-prefix")


def test_metric_recording_failures_do_not_break_wsgi_app(caplog: pytest.LogCaptureFixture) -> None:
    registry = MetricRegistry()
    metrics = HTTPMetrics.create(registry, max_series=1)
    metrics.requests.inc(method="DELETE", status_class="5xx")

    def app(_environ: Mapping[str, object], start_response: StartResponse) -> Iterable[bytes]:
        start_response("200 OK", [])
        return [b"ok"]

    wrapped = instrument_wsgi(app, registry, metrics=metrics)
    assert b"".join(wrapped({"REQUEST_METHOD": "GET"}, _start_response)) == b"ok"
    assert "failed to record HTTP request completion" in caplog.text


def test_asgi_middleware_records_success_failure_and_ignores_websocket() -> None:
    registry = MetricRegistry()
    calls: list[str] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request"}

    async def send(_message: dict[str, object]) -> None:
        return None

    async def app(scope: ASGIScope, _receive: ASGIReceive, app_send: ASGISend) -> None:
        calls.append(str(scope["type"]))
        if scope.get("path") == "/fail":
            raise RuntimeError("asgi failed")
        if scope["type"] == "http":
            await app_send({"type": "http.response.start", "status": 201})
            await app_send({"type": "http.response.body", "body": b"ok"})

    wrapped = instrument_asgi(app, registry)
    asyncio.run(
        wrapped(
            {"type": "http", "method": "GET", "path": "/ok"},
            receive,
            send,
        )
    )
    with pytest.raises(RuntimeError, match="asgi failed"):
        asyncio.run(
            wrapped(
                {"type": "http", "method": "DELETE", "path": "/fail"},
                receive,
                send,
            )
        )
    asyncio.run(wrapped({"type": "websocket"}, receive, send))

    samples = registry.query("http_server_requests_total")
    assert {(sample.labels["method"], sample.labels["status_class"]) for sample in samples} == {
        ("DELETE", "5xx"),
        ("GET", "2xx"),
    }
    assert calls == ["http", "http", "websocket"]
