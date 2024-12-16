import logging
from typing import Any
import structlog
from structlog.types import Processor, EventDict

def setup_logging(app_name: str, version: str, log_level: str) -> None:
    # use iso format timestamp
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    # structlog default message key is event, this uses message instead
    event_to_message = structlog.processors.EventRenamer(to="message")

    # uvicorn loggers add a color_message key that is a duplicate of the message
    def drop_color_message_key(_, __, event_dict: EventDict) -> EventDict:
        event_dict.pop("color_message", None)
        return event_dict
    
    # add app name and version to every log
    def add_app_context(_, __, event_dict: EventDict) -> EventDict:
        event_dict["app_name"] = app_name
        event_dict["@version"] = version
        return event_dict

    shared_processors: list[Processor] = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            add_app_context,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ExtraAdder(),
            drop_color_message_key,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            event_to_message,
        ]

    structlog.configure(
        processors = shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory = structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use = True,
    )

    log_renderer = structlog.processors.JSONRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        # These run ONLY on `logging` entries that do NOT originate within
        # structlog.
        foreign_pre_chain=shared_processors,
        # These run on ALL entries after the pre_chain is done.
        processors=[
            # Remove _record & _from_structlog.
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            log_renderer,
        ],
    )

    # Reconfigure the root logger to use our structlog formatter, effectively emitting the logs via structlog
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    for _log in ["uvicorn", "uvicorn.error"]:
        # Make sure the logs are handled by the root logger
        logging.getLogger(_log).handlers.clear()
        logging.getLogger(_log).propagate = True

    # Silence uvicorn access log. We create a more context specific log
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False