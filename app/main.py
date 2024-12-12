from fastapi import FastAPI
from app.config import Config
from app.router import router
from app.logger import setup_logging
from app.middleware import StructLogMiddleware
from asgi_correlation_id import CorrelationIdMiddleware
import uvicorn
import logging

app_config = Config()
app = FastAPI()
app.include_router(router)
app.add_middleware(StructLogMiddleware)
app.add_middleware(CorrelationIdMiddleware)

server = uvicorn.Server(config = uvicorn.Config(
    app,
    host = app_config.host,
    port = int(app_config.port),
))

# setting up logging here so that uvicorn loggers are already created and can be configured as we want
setup_logging(app_config.app_name, app_config.version, app_config.log_level)

def main():
    server.run()

if __name__ == "__main__":
    main()