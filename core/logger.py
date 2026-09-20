import logging
import sys
from typing import Optional
from core.config import settings

def setup_logger(name: str = "job_agent") -> logging.Logger:
    """
    Returns a configured standard Python logger with consistent formatting.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
        logger.setLevel(level)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

    return logger

class DatabaseLogHandler(logging.Handler):
    """
    Custom logging handler that persists log records to the `run_logs` table
    for real-time streaming in the frontend web terminal.
    """
    def __init__(self, run_id: int):
        super().__init__()
        self.run_id = run_id
        formatter = logging.Formatter("%(message)s")
        self.setFormatter(formatter)

    def emit(self, record):
        try:
            from repositories.pipeline_run_repository import PipelineRunRepository
            msg = self.format(record)
            PipelineRunRepository.append_pipeline_log(self.run_id, msg)
        except Exception:
            pass

def get_pipeline_logger(run_id: Optional[int] = None) -> logging.Logger:
    """
    Factory creating a pipeline logger that writes both to stdout and to database.
    """
    logger_name = f"pipeline.{run_id}" if run_id else "pipeline.standalone"
    logger = setup_logger(logger_name)

    if run_id:
        has_db_handler = any(isinstance(h, DatabaseLogHandler) and h.run_id == run_id for h in logger.handlers)
        if not has_db_handler:
            db_handler = DatabaseLogHandler(run_id)
            logger.addHandler(db_handler)

    return logger
