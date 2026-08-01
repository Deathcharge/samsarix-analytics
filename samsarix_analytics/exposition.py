# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Dependency-free HTTP exposition for :class:`MetricRegistry`."""

from __future__ import annotations

import hmac
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from threading import Lock, Thread
from typing import Protocol, cast
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from .monitoring.metrics import MetricError, MetricRegistry

logger = logging.getLogger(__name__)

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
_PLAIN_CONTENT_TYPE = "text/plain; charset=utf-8"
_ALLOWED_METHODS = "GET, HEAD, OPTIONS"
_DEFAULT_MAX_RESPONSE_BYTES = 10 * 1024 * 1024


class StartResponse(Protocol):
    """The WSGI ``start_response`` callable used by :func:`make_wsgi_app`."""

    def __call__(
        self,
        status: str,
        response_headers: list[tuple[str, str]],
        exc_info: object | None = None,
    ) -> Callable[[bytes], object]: ...


WSGIApp = Callable[[Mapping[str, object], StartResponse], Iterable[bytes]]
ASGIScope = Mapping[str, object]
ASGIReceive = Callable[[], Awaitable[dict[str, object]]]
ASGISend = Callable[[dict[str, object]], Awaitable[None]]
ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]


@dataclass(frozen=True)
class _Response:
    status: str
    body: bytes
    content_type: str = _PLAIN_CONTENT_TYPE
    headers: tuple[tuple[str, str], ...] = ()

    def http_headers(self) -> list[tuple[str, str]]:
        return [
            ("Content-Type", self.content_type),
            ("Content-Length", str(len(self.body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            *self.headers,
        ]


def _validate_path(path: str) -> str:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("metrics path must be an absolute HTTP path")
    if "?" in path or "#" in path or any(ord(character) < 32 for character in path):
        raise ValueError("metrics path cannot contain a query, fragment, or control character")
    return path


def _validate_token(bearer_token: str | None) -> str | None:
    if bearer_token is None:
        return None
    if not isinstance(bearer_token, str) or not bearer_token:
        raise ValueError("bearer_token must be a non-empty string")
    if (
        len(bearer_token) > 4096
        or not bearer_token.isascii()
        or any(not 33 <= ord(character) <= 126 for character in bearer_token)
    ):
        raise ValueError("bearer_token must contain only visible ASCII characters")
    return bearer_token


def _validate_max_response_bytes(max_response_bytes: int) -> int:
    if (
        isinstance(max_response_bytes, bool)
        or not isinstance(max_response_bytes, int)
        or max_response_bytes < 1
    ):
        raise ValueError("max_response_bytes must be a positive integer")
    return max_response_bytes


def _is_authorized(authorization: str | None, bearer_token: str | None) -> bool:
    if bearer_token is None:
        return True
    if authorization is None or not authorization.startswith("Bearer "):
        return False
    provided = authorization[7:]
    if not provided.isascii():
        return False
    return hmac.compare_digest(provided.encode("ascii"), bearer_token.encode("ascii"))


def _response_for(
    registry: MetricRegistry,
    *,
    configured_path: str,
    request_path: str,
    method: str,
    authorization: str | None,
    bearer_token: str | None,
    max_response_bytes: int,
) -> _Response:
    if request_path != configured_path:
        return _Response("404 Not Found", b"# not found\n")
    if method not in {"GET", "HEAD", "OPTIONS"}:
        return _Response(
            "405 Method Not Allowed",
            b"# method not allowed; use GET, HEAD, or OPTIONS\n",
            headers=(("Allow", _ALLOWED_METHODS),),
        )
    if method == "OPTIONS":
        return _Response("200 OK", b"", headers=(("Allow", _ALLOWED_METHODS),))
    if not _is_authorized(authorization, bearer_token):
        return _Response(
            "401 Unauthorized",
            b"# unauthorized\n",
            headers=(("WWW-Authenticate", 'Bearer realm="metrics"'),),
        )
    try:
        body = registry.to_prometheus(max_bytes=max_response_bytes).encode("utf-8")
    except MetricError as exc:
        logger.warning("refused to render Prometheus metrics: %s", exc)
        return _Response(
            "503 Service Unavailable",
            b"# metrics output exceeds configured response limit\n",
        )
    except Exception:
        logger.exception("failed to render Prometheus metrics")
        return _Response("500 Internal Server Error", b"# metrics rendering failed\n")
    return _Response("200 OK", body, PROMETHEUS_CONTENT_TYPE)


def make_wsgi_app(
    registry: MetricRegistry,
    *,
    path: str = "/metrics",
    bearer_token: str | None = None,
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
) -> WSGIApp:
    """Create a WSGI metrics endpoint with optional bearer-token authentication."""

    configured_path = _validate_path(path)
    configured_token = _validate_token(bearer_token)
    configured_max_bytes = _validate_max_response_bytes(max_response_bytes)

    def app(environ: Mapping[str, object], start_response: StartResponse) -> Iterable[bytes]:
        method_value = environ.get("REQUEST_METHOD", "GET")
        path_value = environ.get("PATH_INFO", "")
        authorization_value = environ.get("HTTP_AUTHORIZATION")
        method = method_value.upper() if isinstance(method_value, str) else ""
        response = _response_for(
            registry,
            configured_path=configured_path,
            request_path=path_value if isinstance(path_value, str) else "",
            method=method,
            authorization=(authorization_value if isinstance(authorization_value, str) else None),
            bearer_token=configured_token,
            max_response_bytes=configured_max_bytes,
        )
        start_response(response.status, response.http_headers())
        return [] if method == "HEAD" else [response.body]

    return app


def _asgi_header(scope: ASGIScope, name: bytes) -> str | None:
    raw_headers = scope.get("headers", ())
    if not isinstance(raw_headers, (list, tuple)):
        return None
    for item in raw_headers:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        raw_name, raw_value = item
        if (
            isinstance(raw_name, bytes)
            and isinstance(raw_value, bytes)
            and raw_name.lower() == name
        ):
            try:
                return raw_value.decode("latin-1")
            except UnicodeDecodeError:
                return None
    return None


def make_asgi_app(
    registry: MetricRegistry,
    *,
    path: str = "/metrics",
    bearer_token: str | None = None,
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
) -> ASGIApp:
    """Create an ASGI metrics endpoint with optional bearer-token authentication."""

    configured_path = _validate_path(path)
    configured_token = _validate_token(bearer_token)
    configured_max_bytes = _validate_max_response_bytes(max_response_bytes)

    async def app(scope: ASGIScope, _receive: ASGIReceive, send: ASGISend) -> None:
        if scope.get("type") != "http":
            raise ValueError("the metrics ASGI app supports only HTTP scopes")
        method_value = scope.get("method", "GET")
        path_value = scope.get("path", "")
        method = method_value.upper() if isinstance(method_value, str) else ""
        response = _response_for(
            registry,
            configured_path=configured_path,
            request_path=path_value if isinstance(path_value, str) else "",
            method=method,
            authorization=_asgi_header(scope, b"authorization"),
            bearer_token=configured_token,
            max_response_bytes=configured_max_bytes,
        )
        await send(
            {
                "type": "http.response.start",
                "status": int(response.status[:3]),
                "headers": [
                    (name.lower().encode("ascii"), value.encode("latin-1"))
                    for name, value in response.http_headers()
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"" if method == "HEAD" else response.body,
            }
        )

    return app


class _QuietRequestHandler(WSGIRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        return None


@dataclass
class MetricsServer:
    """A running loopback metrics server returned by :func:`start_metrics_server`."""

    host: str
    port: int
    path: str
    _server: WSGIServer = field(repr=False)
    _thread: Thread = field(repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _close_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}{self.path}"

    def close(self, *, timeout: float = 5.0) -> None:
        """Stop the server, close its socket, and wait for its thread."""

        if timeout < 0:
            raise ValueError("timeout must be non-negative")
        with self._close_lock:
            if self._closed:
                return
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout)
            if self._thread.is_alive():
                raise TimeoutError("metrics server did not stop before the timeout")
            self._closed = True

    def __enter__(self) -> MetricsServer:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()


def start_metrics_server(
    registry: MetricRegistry,
    *,
    host: str = "127.0.0.1",
    port: int = 9464,
    path: str = "/metrics",
    bearer_token: str | None = None,
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
) -> MetricsServer:
    """Start a stdlib WSGI server; loopback is the secure default binding."""

    if not isinstance(host, str) or not host:
        raise ValueError("host must be a non-empty string")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("port must be an integer between 0 and 65535")
    configured_path = _validate_path(path)
    app = make_wsgi_app(
        registry,
        path=configured_path,
        bearer_token=bearer_token,
        max_response_bytes=max_response_bytes,
    )
    server = make_server(
        host, port, cast(Callable[..., Iterable[bytes]], app), handler_class=_QuietRequestHandler
    )
    bound_host, bound_port = server.server_address[:2]
    thread = Thread(target=server.serve_forever, name="samsarix-metrics", daemon=True)
    thread.start()
    return MetricsServer(str(bound_host), int(bound_port), configured_path, server, thread)


__all__ = [
    "PROMETHEUS_CONTENT_TYPE",
    "ASGIApp",
    "MetricsServer",
    "WSGIApp",
    "make_asgi_app",
    "make_wsgi_app",
    "start_metrics_server",
]
