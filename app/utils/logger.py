
import logging
import sys
from app.utils.config import config


def get_logger(name: str) -> logging.Logger:
    """Returns a configured logger for any module.    
    Usage:
        from app.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Pipeline started")
        logger.error("SQL validation failed: %s", error_msg)    
    __name__ gives the module path e.g. 'app.graph.nodes.#'
    This tells you exactly which file the log came from."""

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger