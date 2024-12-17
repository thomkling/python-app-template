import time
from typing import TypedDict

import structlog
from asgi_correlation_id import correlation_id
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from uvicorn.protocols.utils import get_path_with_query_string
from prometheus_client import Histogram, Counter, Gauge

# standard http prometheus metrics
request_duration = Histogram(
    "python_http_duration_seconds",
    "Duration of HTTP requests by path",
    labelnames=["method", "path"],
)
request_counter = Counter(
    "python_api_requests_total",
    "A counter for requests",
    labelnames=["code", "method", "path"],
)
active_request_gauge = Gauge(
    "python_http_server_active_requests",
    "A counter for active http request count",
    labelnames=["method", "path"],
)


# get app logger
app_logger = structlog.stdlib.get_logger("app_logs")

# url segment approved_list for sanitization
approved_list = ["ping", "metrics", "widget", "exception"]

class RequestInfo(TypedDict, total=False):
    status_code: int
    start_time: float

class InstrumentationMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        pass

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # If the request is not an HTTP request, we don't need to do anything special
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        
        # clear possibly pre-existing contextvars and bind request id which should exist from CorrelationMiddleware
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=correlation_id.get())

        info = RequestInfo()

        # Inner send function
        async def inner_send(message):
            if message["type"] == "http.response.start":
                info["status_code"] = message["status"]
            await send(message)

        # gather start time stamp
        info["start_time"] = time.perf_counter()

        try:
            # increment active gauge
            active_request_gauge.labels(scope["method"], sanitize_url(scope["path"], approved_list)).inc()
            await self.app(scope, receive, inner_send)
        except Exception as e:
            # catch unhandled exceptions
            app_logger.exception(
                "An unhandled exception was caught by last resort middleware",
                exception_class=e.__class__.__name__,
                exc_info=e,
                stack_info=True,
            )
            info["status_code"] = 500
            response = JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred.",
                },
            )
            await response(scope, receive, send)
        finally:
            # calculate request process time and observe the metric
            http_method = scope["method"]
            route = sanitize_url(scope["path"], approved_list)
            process_time = time.perf_counter() - info["start_time"]
            request_duration.labels(http_method, route).observe(process_time)

            # decrement active guage
            active_request_gauge.labels(http_method, route).dec()

            # increment counter
            if "status_code" in info:
                request_counter.labels(info["status_code"], http_method, route).inc()

            # Create an app log for "Request IN" that includes basic request information for every request except
            # those for /ping /health /metrics endpoints
            path = scope["path"]
            if path in ["/ping", "/health", "/metrics"]:
                client_host, client_port = scope["client"]
                http_version = scope["http_version"]
                app_logger.info(
                    f"Request IN - {path}",
                    http={
                        "url": request.url,
                        "status_code": info.get("status_code"),
                        "method": http_method,
                        "request_id": correlation_id.get(),
                        "version": http_version,
                    },
                    network={"client": {"ip": client_host, "port": client_port}},
                    duration=process_time,
                )

# sanitize_url replaces segments of the path with an asterisk if that segment is not in the approved_list
# we do this so we can track metrics by endpoint rather than by unique url
def sanitize_url(url: str, approved_list: list[str]) -> str:
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    # first str in list is an empty str
    if len(path_parts) > 2:
        for i, segment in enumerate(path_parts):
            if segment != '' and segment not in approved_list:
                path_parts[i] = '*'
    sanitized_url = '/'.join(path_parts)
    return sanitized_url
