import logging
import sys

def setup_logger():
    """
    Configures a logger to output to the console (stdout).
    This is for environments where file logging might be restricted.
    The output can be captured by redirecting the process's stdout.
    """
    logger = logging.getLogger("agent_logger")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Clear existing handlers to avoid duplication
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger

log = setup_logger()
