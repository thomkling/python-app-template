from fastapi import FastAPI
from app.config import Config
from app.router import router
from app.logger import setup_logging
from app.middleware import InstrumentationMiddleware
from asgi_correlation_id import CorrelationIdMiddleware
from prometheus_client import make_asgi_app
from starlette.routing import Mount
import uvicorn
import structlog
import re

# create app
app_config = Config()
app = FastAPI()

# create metrics route and registry
metrics_route = Mount("/metrics", make_asgi_app())
metrics_route.path_regex = re.compile("^/metrics(?P<path>.*)$")
app.routes.append(metrics_route)

# add router and middleware
app.include_router(router)
app.add_middleware(InstrumentationMiddleware)
app.add_middleware(CorrelationIdMiddleware)

# create uvicorn server with config
server = uvicorn.Server(config = uvicorn.Config(
    app,
    host = app_config.host,
    port = int(app_config.port),
))

# setting up logging here so that uvicorn loggers are already created and can be configured as we want
setup_logging(app_config.app_name, app_config.version, app_config.log_level)

log = structlog.stdlib.get_logger("app_logs")

def main():
    log.info(f"Starting service on port {app_config.port}...")
    server.run()

if __name__ == "__main__":
    main()