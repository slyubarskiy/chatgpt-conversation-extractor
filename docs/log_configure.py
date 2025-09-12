
import logging
from pathlib import Path
import datetime as dt
import os 

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(module)s:%(funcName)s] - %(message)s"
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%f'[:-3]
LOG_PROCESSING_FILE_NAME = "res_uki_sales_reporting_processing.log"
LOG_WARNING_FILE_NAME = "res_uki_sales_reporting_warnings.log"
LOG_CRITICAL_FILE_NAME = "res_uki_sales_reporting_critical.log"
NOTEBOOK_CONSOLE_LOGGING_LEVEL = logging.INFO

PROJECT_ROOT = os.path.dirname(Path(os.getcwd()).resolve()).replace("\\", "/")


LOGS_DIR = PROJECT_ROOT  + "/logs"
# print(os.path.isdir(os.mkdir(LOGS_DIR))) # Ensure logs directory exists

# Form log file paths
LOG_PROCESSING_FILE_PATH = LOGS_DIR +  LOG_PROCESSING_FILE_NAME
LOG_WARNING_FILE_PATH = LOGS_DIR  + LOG_WARNING_FILE_NAME
LOG_CRITICAL_FILE_PATH = LOGS_DIR + LOG_CRITICAL_FILE_NAME


# Define function for determining if the code runs in notebook so that the testing handling adjustes to on-screen when in notebook.



# Logging Init


class CustomFormatter(logging.Formatter):
    
    def formatTime(self, record, datefmt=None):
            """Format the log time with milliseconds."""
            dt_object = dt.datetime.fromtimestamp(record.created)
            return dt_object.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # Keep only milliseconds  
         
    def format(self, record):
        # Check if the execution context is the main module
        if record.module == '__main__':
            record.module = 'main_module'
        return logging.Formatter.format(self, record)

# Create a custom tqdm logger that won't interfere with progress bars
class TqdmConsoleHandler(logging.StreamHandler):
    """
    A handler that writes to console without disrupting tqdm progress bars.
    Uses tqdm.write() instead of direct writes to sys.stdout/stderr.
    """
    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
            
def configure_logging(level=logging.INFO, log_format=LOG_FORMAT, log_date_format=LOG_DATE_FORMAT, use_tqdm_handler=None):
    """
    Configures logging (both initial setup and reconfiguration).

    If logging is already set up, it removes existing handlers and applies new settings.

    Args:
        level (int): Logging level (default: INFO)
        log_format (str): Log format string (default: predefined LOG_FORMAT)
        log_date_format (str): Date format string (default: predefined LOG_DATE_FORMAT)
        use_tqdm_handler (bool): Whether to use tqdm-compatible console handler. 
                               If None, auto-detects Jupyter notebook environment.
    """
    

    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Create and configure file handlers
    file_handler = logging.FileHandler(LOG_PROCESSING_FILE_PATH)
    file_handler.setLevel(logging.INFO)

    warning_handler = logging.FileHandler(LOG_WARNING_FILE_PATH)
    warning_handler.setLevel(logging.WARNING)

    critical_handler = logging.FileHandler(LOG_CRITICAL_FILE_PATH)
    critical_handler.setLevel(logging.CRITICAL)
    
    # Create console handler - either standard or tqdm-compatible
    if use_tqdm_handler:
        console_handler = TqdmConsoleHandler()
    else:
        console_handler = logging.StreamHandler()
        
    # Create console handler
    console_handler.setLevel(level)  # PLACEHOLDER - option to set only warnings/errors in Jupyter

    # Set the format for all handlers
    formatter = CustomFormatter(log_format, datefmt=log_date_format)
    for handler in [file_handler, warning_handler, critical_handler, console_handler]:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    if use_tqdm_handler:
        logging.debug("Using tqdm-compatible console handler for progress bar support")

# REMOVE FOR BATCH EXECUTION
# Reconfigure logging to allow for changing while in Notebooks 

logging.info("INIT: Detected Jupyter Notebook environment.")
configure_logging(logging.DEBUG, log_format = LOG_FORMAT, log_date_format = LOG_DATE_FORMAT)
