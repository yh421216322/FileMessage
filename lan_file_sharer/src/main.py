# Main entry point for the LAN File Sharer application
import logging # Import logging here as well for initial messages if needed
from .logger_setup import setup_logging
from .ui.app import run_app # Use relative import if main.py is treated as part of the package

if __name__ == "__main__":
    # Call logging setup before anything else that might log.
    setup_logging()
    
    # Example: Get a logger for main.py itself if you want to log directly from here
    logger = logging.getLogger(__name__)
    logger.info("LAN File Sharer application starting...")
    
    try:
        run_app()
        logger.info("Application exited normally.")
    except Exception as e:
        logger.critical("Application terminated due to an unhandled exception.", exc_info=True)
        # Optionally, you might want to show a system-level error dialog here if the UI isn't available.
        # For now, logging is the primary goal.
