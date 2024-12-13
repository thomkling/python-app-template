import time
from typing import TypedDict

import structlog
from asgi_correlation_id import correlation_id
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


# app and access loggers
app_logger = structlog.stdlib.get_logger("app_logs")
access_logger = structlog.stdlib.get_logger("access_logs")

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
            active_request_gauge.labels(scope["method"], get_path_with_query_string(scope)).inc()
            await self.app(scope, receive, inner_send)
        except Exception as e:
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
            url = get_path_with_query_string(scope)
            process_time = time.perf_counter() - info["start_time"]
            request_duration.labels(http_method, url).observe(process_time)

            # decrement active guage
            active_request_gauge.labels(http_method, url).dec()

            # increment counter
            request_counter.labels(info["status_code"], http_method, url).inc()

            # Recreate the Uvicorn access log format, but add all parameters as structured information
            client_host, client_port = scope["client"]
            http_version = scope["http_version"]
            access_logger.info(
                f"""{client_host}:{client_port} - "{http_method} {scope["path"]} HTTP/{http_version}" {info["status_code"]}""",
                http={
                    "url": str(url),
                    "status_code": info["status_code"],
                    "method": http_method,
                    "request_id": correlation_id.get(),
                    "version": http_version,
                },
                network={"client": {"ip": client_host, "port": client_port}},
                duration=process_time,
            )
