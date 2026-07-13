"""Prometheus HTTP request metrics middleware."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from barekat.observability.metrics import HTTP_LATENCY, HTTP_REQUESTS


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        endpoint = request.url.path
        # Collapse path params for cardinality control
        if endpoint.startswith("/api/v1/"):
            parts = endpoint.split("/")
            if len(parts) > 4 and parts[4].isdigit():
                parts[4] = "{id}"
            endpoint = "/".join(parts[:6])

        HTTP_REQUESTS.labels(
            method=request.method,
            endpoint=endpoint,
            status=str(response.status_code),
        ).inc()
        HTTP_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)
        return response
