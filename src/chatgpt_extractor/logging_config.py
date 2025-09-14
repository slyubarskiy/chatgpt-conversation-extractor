"""
Production-ready logging configuration for ChatGPT Conversation Extractor.

This module provides structured logging with multiple handlers for different
severity levels, progress bar compatibility, and containerization support.
"""

import logging
import logging.handlers
import os
import sys
import json
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Union


DEFAULT_LOG_FORMAT = (
    "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(funcName)s:%(lineno)d] - %(message)s"
)
JSON_LOG_FORMAT = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "function": "%(funcName)s", "line": %(lineno)d, "message": "%(message)s"}'
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOG_DIR_NAME = "logs"
LOG_PROCESSING_FILE = "extraction_processing.log"
LOG_ERROR_FILE = "extraction_errors.log"
LOG_CRITICAL_FILE = "extraction_critical.log"

MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5


class MillisecondFormatter(logging.Formatter):
    """Custom formatter with millisecond precision timestamps."""

    def formatTime(self, record, datefmt=None):
        """Format time with milliseconds."""
        dt = datetime.fromtimestamp(record.created)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            s = dt.strftime("%Y-%m-%d %H:%M:%S")
        s = f"{s}.{int(record.msecs):03d}"
        return s

    def format(self, record):
        # __main__ becomes 'main' for cleaner log output
        if record.module == "__main__":
            record.module = "main"

        # Add exception info if present
        if record.exc_info:
            # Don't pass exc_info to parent to avoid duplicate traceback
            exc_info = record.exc_info
            record.exc_info = None
            result = super().format(record)
            if exc_info:
                result += (
                    f"\nTraceback:\n{''.join(traceback.format_exception(*exc_info))}"
                )
            return result

        return super().format(record)


class TqdmLoggingHandler(logging.StreamHandler):
    """
    Logging handler compatible with tqdm progress bars.
    Writes log messages without disrupting progress bar display.
    """

    def emit(self, record):
        try:
            # Import tqdm only when needed
            try:
                from tqdm import tqdm

                msg = self.format(record)
                tqdm.write(msg, file=self.stream)
            except ImportError:
                # Fallback to regular output if tqdm not available
                super().emit(record)
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging in containerized environments."""

    def format(self, record):
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "process": record.process,
            "thread": record.thread,
        }

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": "".join(traceback.format_exception(*record.exc_info)),
            }

        # Add extra fields if any
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
            ]:
                log_obj[key] = value

        return json.dumps(log_obj, default=str)


def setup_logging(
    level: int = logging.INFO,
    log_dir: Optional[Path] = None,
    use_json: bool = False,
    use_tqdm: bool = False,
    console_level: Optional[int] = None,
    disable_file_logging: bool = False,
) -> logging.Logger:
    """
    Configure logging for the ChatGPT Conversation Extractor.

    Args:
        level: Base logging level (default: INFO)
        log_dir: Directory for log files (default: ./logs)
        use_json: Use JSON formatting for container environments
        use_tqdm: Use tqdm-compatible handler for progress bars
        console_level: Separate console logging level (default: same as level)
        disable_file_logging: Disable file logging (for testing/containers)

    Returns:
        Configured logger instance
    """

    # Set up root logger
    root_logger = logging.getLogger("chatgpt_extractor")
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    # Determine console level
    if console_level is None:
        console_level = level

    # Set up formatters
    formatter: Union[JSONFormatter, MillisecondFormatter]
    if use_json:
        formatter = JSONFormatter()
    else:
        formatter = MillisecondFormatter(DEFAULT_LOG_FORMAT, datefmt=DATE_FORMAT)

    # Console handler
    console_handler: Union[TqdmLoggingHandler, logging.StreamHandler]
    if use_tqdm:
        console_handler = TqdmLoggingHandler(sys.stdout)
    else:
        console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handlers (if not disabled)
    if not disable_file_logging:
        if log_dir is None:
            # Find the project root (where the script is located)
            # This ensures logs are always created in the same place
            script_dir = Path(__file__).parent.parent.parent  # Up to project root
            log_dir = script_dir / LOG_DIR_NAME
        else:
            log_dir = Path(log_dir)

        # Create log directory with error handling
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            root_logger.error(f"Failed to create log directory {log_dir}: {e}")
            return root_logger

        # Processing log (INFO and above)
        try:
            processing_handler = logging.handlers.RotatingFileHandler(
                log_dir / LOG_PROCESSING_FILE,
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
            )
            processing_handler.setLevel(logging.INFO)
            processing_handler.setFormatter(formatter)
            root_logger.addHandler(processing_handler)
        except Exception as e:
            root_logger.error(f"Failed to create processing log handler: {e}")

        # Error log (ERROR and above)
        try:
            error_handler = logging.handlers.RotatingFileHandler(
                log_dir / LOG_ERROR_FILE,
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            root_logger.addHandler(error_handler)
        except Exception as e:
            root_logger.error(f"Failed to create error log handler: {e}")

        # Critical log (CRITICAL only)
        try:
            critical_handler = logging.handlers.RotatingFileHandler(
                log_dir / LOG_CRITICAL_FILE,
                maxBytes=MAX_LOG_SIZE // 2,  # Smaller size for critical
                backupCount=BACKUP_COUNT,
            )
            critical_handler.setLevel(logging.CRITICAL)
            critical_handler.setFormatter(formatter)
            root_logger.addHandler(critical_handler)
        except Exception as e:
            root_logger.error(f"Failed to create critical log handler: {e}")

    # Log initial configuration
    root_logger.info(
        f"Logging configured - Level: {logging.getLevelName(level)}, "
        f"JSON: {use_json}, tqdm: {use_tqdm}, "
        f"File logging: {not disable_file_logging}"
    )

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(f"chatgpt_extractor.{name}")


def log_exception(logger: logging.Logger, exc: Exception, context: str = "") -> None:
    """
    Log an exception with full traceback.

    Args:
        logger: Logger instance
        exc: Exception to log
        context: Additional context about where/why the exception occurred
    """
    exc_type = type(exc).__name__
    exc_msg = str(exc)
    exc_traceback = traceback.format_exc()

    log_msg = (
        f"Exception in {context}: {exc_type}: {exc_msg}"
        if context
        else f"{exc_type}: {exc_msg}"
    )

    logger.error(
        log_msg,
        extra={
            "exception_type": exc_type,
            "exception_message": exc_msg,
            "exception_traceback": exc_traceback,
            "context": context,
        },
        exc_info=True,
    )


# Convenience function for quick setup
def configure_production_logging(debug: bool = False) -> logging.Logger:
    """
    Quick setup for production logging with sensible defaults.

    Args:
        debug: Enable debug logging

    Returns:
        Configured logger
    """
    level = logging.DEBUG if debug else logging.INFO

    # Detect if running in container (common env vars)
    in_container = any(
        key in os.environ for key in ["KUBERNETES_SERVICE_HOST", "DOCKER_CONTAINER"]
    )

    return setup_logging(
        level=level,
        use_json=in_container,
        use_tqdm=not in_container and sys.stdout.isatty(),
        console_level=logging.WARNING if not debug else logging.DEBUG,
    )


if __name__ == "__main__":
    # Example usage
    logger = configure_production_logging(debug=True)
    logger.info("Logging system initialized")
    logger.debug("Debug message")
    logger.warning("Warning message")

    try:
        1 / 0
    except Exception as e:
        log_exception(logger, e, "division test")
