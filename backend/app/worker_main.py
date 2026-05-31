import logging

from app.core.logging_config import setup_logging
from app.workers.paper_worker import run_worker_forever

setup_logging()
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Starting paper background worker")
    try:
        run_worker_forever()
    except KeyboardInterrupt:
        logger.info("Paper background worker stopped by user")
