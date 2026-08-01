# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Bounded, framework-neutral HTTP server instrumentation."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import cast

from .exposition import ASGIApp, ASGIReceive, ASGIScope, ASGISend, StartResponse, WSGIApp
from .monitoring.metrics import Counter, Gauge, Histogram, MetricError, MetricRegistry

logger = logging.getLogger(__name__)

_KNOWN_METHODS = frozenset(
    {"CONNECT", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"}
)
_DEFAULT_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)


def _method(value: object) -> str:
    normalized = value.upper() if isinstance(value, str) else ""
    return normalized if normalized in _KNOWN_METHODS else "OTHER"


def _status_class(value: object) -> str:
    if isinstance(value, bool):
        return "invalid"
    if isinstance(value, int):
        status = value
    elif isinstance(value, str) and len(value) >= 3 and value[:3].isdigit():
        status = int(value[:3])
    else:
        return "invalid"
    return f"{status // 100}xx" if 100 <= status <= 599 else "invalid"


@dataclass(frozen=True)
class HTTPMetrics:
    """The three instruments shared by WSGI and ASGI middleware."""

    requests: Counter
    duration: Histogram
    active: Gauge

    @classmethod
    def create(
        cls,
        registry: MetricRegistry,
        *,
        prefix: str = "http_server",
        max_series: int = 64,
        duration_buckets: Sequence[float] = _DEFAULT_DURATION_BUCKETS,
    ) -> HTTPMetrics:
        """Create or reuse a bounded standard HTTP instrument set."""

        return cls(
            requests=registry.counter(
                f"{prefix}_requests_total",
                "Completed HTTP server requests",
                ("method", "status_class"),
                max_series=max_series,
            ),
            duration=registry.histogram(
                f"{prefix}_request_duration_seconds",
                "HTTP server request duration in seconds",
                ("method", "status_class"),
                buckets=duration_buckets,
                max_series=max_series,
            ),
            active=registry.gauge(
                f"{prefix}_active_requests",
                "HTTP server requests currently in progress",
                ("method",),
                max_series=min(max_series, len(_KNOWN_METHODS) + 1),
            ),
        )

    def begin(self, method: str) -> bool:
        """Record request entry and report whether an active value was changed."""

        try:
            self.active.inc(method=method)
        except MetricError:
            logger.exception("failed to record HTTP request entry")
            return False
        return True

    def finish(
        self,
        method: str,
        status_class: str,
        elapsed_seconds: float,
        *,
        active_recorded: bool,
    ) -> None:
        """Record request completion without allowing metric failures to escape."""

        operations: list[Callable[[], None]] = [
            lambda: self.requests.inc(method=method, status_class=status_class),
            lambda: self.duration.observe(
                elapsed_seconds, method=method, status_class=status_class
            ),
        ]
        if active_recorded:
            operations.insert(0, lambda: self.active.dec(method=method))
        for operation in operations:
            try:
                operation()
            except MetricError:
                logger.exception("failed to record HTTP request completion")


def instrument_wsgi(
    app: WSGIApp,
    registry: MetricRegistry,
    *,
    metrics: HTTPMetrics | None = None,
) -> WSGIApp:
    """Wrap a WSGI app with bounded request count, duration, and active metrics."""

    http_metrics = metrics or HTTPMetrics.create(registry)

    def middleware(environ: Mapping[str, object], start_response: StartResponse) -> Iterable[bytes]:
        method = _method(environ.get("REQUEST_METHOD"))
        started = perf_counter()
        active_recorded = http_metrics.begin(method)
        status_class = "5xx"
        finalized = False

        def capture_status(
            status: str,
            headers: list[tuple[str, str]],
            exc_info: object | None = None,
        ) -> object:
            nonlocal status_class
            status_class = _status_class(status)
            return start_response(status, headers, exc_info)

        def finalize() -> None:
            nonlocal finalized
            if finalized:
                return
            finalized = True
            http_metrics.finish(
                method,
                status_class,
                perf_counter() - started,
                active_recorded=active_recorded,
            )

        try:
            response = app(environ, cast(StartResponse, capture_status))
        except BaseException:
            finalize()
            raise

        def body() -> Iterable[bytes]:
            try:
                yield from response
            finally:
                try:
                    close = getattr(response, "close", None)
                    if close is not None:
                        close()
                finally:
                    finalize()

        return body()

    return middleware


def instrument_asgi(
    app: ASGIApp,
    registry: MetricRegistry,
    *,
    metrics: HTTPMetrics | None = None,
) -> ASGIApp:
    """Wrap an ASGI app while leaving non-HTTP scopes untouched."""

    http_metrics = metrics or HTTPMetrics.create(registry)

    async def middleware(scope: ASGIScope, receive: ASGIReceive, send: ASGISend) -> None:
        if scope.get("type") != "http":
            await app(scope, receive, send)
            return

        method = _method(scope.get("method"))
        started = perf_counter()
        active_recorded = http_metrics.begin(method)
        status_class = "5xx"

        async def capture_status(message: dict[str, object]) -> None:
            nonlocal status_class
            if message.get("type") == "http.response.start":
                status_class = _status_class(message.get("status"))
            await send(message)

        try:
            await app(scope, receive, capture_status)
        finally:
            http_metrics.finish(
                method,
                status_class,
                perf_counter() - started,
                active_recorded=active_recorded,
            )

    return middleware


__all__ = ["HTTPMetrics", "instrument_asgi", "instrument_wsgi"]
