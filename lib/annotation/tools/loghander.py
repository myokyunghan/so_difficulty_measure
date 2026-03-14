import logging
import os
from datetime import datetime


def get_userlogger(logging_path) : 

    os.makedirs(logging_path, exist_ok=True)

    logger = logging.getLogger("user_logger")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    now = datetime.now()

    file_handler = logging.FileHandler(
        f"{logging_path}/{now.date()}.log"
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger