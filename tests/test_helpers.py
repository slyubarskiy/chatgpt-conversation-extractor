"""
Helper utilities for testing with logging.
"""

import logging
from contextlib import contextmanager
from io import StringIO


@contextmanager
def capture_logs(logger_name='chatgpt_extractor', level=logging.INFO):
    """Context manager to capture log output for testing.
    
    Args:
        logger_name: Name of the logger to capture
        level: Minimum log level to capture
        
    Yields:
        StringIO object containing captured log messages
    """
    # Get the logger
    logger = logging.getLogger(logger_name)
    
    # Create StringIO to capture output
    log_capture = StringIO()
    
    # Create handler with the StringIO
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(level)
    
    # Add simple formatter
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(handler)
    original_level = logger.level
    logger.setLevel(level)
    
    try:
        yield log_capture
    finally:
        # Remove handler and restore original level
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()


def assert_in_logs(log_capture, text):
    """Assert that text appears in captured logs.
    
    Args:
        log_capture: StringIO from capture_logs
        text: Text to search for in logs
    """
    log_content = log_capture.getvalue()
    assert text in log_content, f"'{text}' not found in logs:\n{log_content}"


def get_log_lines(log_capture):
    """Get log content as list of lines.
    
    Args:
        log_capture: StringIO from capture_logs
        
    Returns:
        List of log lines
    """
    return log_capture.getvalue().strip().split('\n') if log_capture.getvalue() else []