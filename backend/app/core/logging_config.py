import logging
import sys

def setup_logging():
    """
    Set up the logging configuration for the application.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
