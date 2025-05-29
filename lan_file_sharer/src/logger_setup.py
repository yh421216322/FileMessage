"""
Configures logging for the LAN File Sharer application.
"""
import logging
import sys
from pathlib import Path
import os

def setup_logging():
    """
    Configures file-based and optional console logging.
    Log file will be stored in a user-writable directory.
    """
    try:
        # Determine user-writable directory for logs
        log_dir_name = ".lan_sharer"
        log_file_name = "lan_sharer.log"
        log_dir_path = Path.home() / log_dir_name

        # Create the directory if it doesn't exist
        log_dir_path.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir_path / log_file_name

        # Configure logging
        log_format = "%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[] # Will add handlers manually
        )

        # Get the root logger
        root_logger = logging.getLogger()
        # Clear any existing handlers on the root logger (important for re-runs or testing)
        if root_logger.hasHandlers():
            root_logger.handlers.clear()


        # File Handler
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)
        
        # Console Handler (optional, good for development)
        if sys.stdout.isatty(): 
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter(log_format))
            root_logger.addHandler(console_handler)

        # Use a logger instance for this module's own messages
        logger = logging.getLogger(__name__)
        logger.info(f"Logging configured. Log file: {log_file_path}")

    except Exception as e:
        # Fallback to basic console logging if setup fails
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        # Use a logger instance here too, though basicConfig might have already set one up
        logger = logging.getLogger(__name__)
        logger.error(f"Error setting up file logging: {e}. Using basic console logging.", exc_info=True)


if __name__ == '__main__':
    # Example of how to use it:
    # Call this function once at the beginning of your application.
    setup_logging()
    
    # Example usage in other modules:
    # import logging
    # logger = logging.getLogger(__name__)
    # logger.info("This is an info message from main example.")
    # logger.warning("This is a warning message from main example.")
    # try:
    #     1 / 0
    # except ZeroDivisionError:
    #     logger.error("A handled error occurred in main example.", exc_info=True) # exc_info=True logs stack trace
    #
    # # Test with a specific module logger
    # test_logger = logging.getLogger("my_module_test")
    # test_logger.info("Info from a specific module logger.")

    logging.info("Logging setup script finished its test run.")
