from fastapi import FastAPI
from app.router import router
from app.logger import setup_logging
from app.middleware import StructLogMiddleware
from asgi_correlation_id import CorrelationIdMiddleware
from uvicorn import Server, Config
import logging



app = FastAPI()
app.include_router(router)
app.add_middleware(StructLogMiddleware)
app.add_middleware(CorrelationIdMiddleware)

server = Server(config = Config(
    app,
    host = "0.0.0.0",
    port = 8080,
))

# setting up logging here so that uvicorn loggers are already created and can be configured as we want
setup_logging()

def main():
    server.run()

if __name__ == "__main__":
    main()