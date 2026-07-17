import logging
import os
from datetime import datetime


# def get_userlogger(logging_path) : 

#     os.makedirs(logging_path, exist_ok=True)

#     logger = logging.getLogger("user_logger")
#     logger.setLevel(logging.INFO)
#     logger.propagate = False

#     if logger.handlers:
#         return logger

#     formatter = logging.Formatter(
#         '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
#     )

#     now = datetime.now()

#     file_handler = logging.FileHandler(
#         f"{logging_path}/{now.date()}.log"
#     )
#     file_handler.setFormatter(formatter)

#     logger.addHandler(file_handler)

#     return logger


# lib/annotation/tools/loghander.py
import logging
import os
from logging.handlers import TimedRotatingFileHandler

_logger_instance = None  # 모듈 레벨 캐시

def init_logger(logging_path: str) -> logging.Logger:
    global _logger_instance

    if _logger_instance is not None:
        return _logger_instance

    os.makedirs(logging_path, exist_ok=True)

    logger = logging.getLogger("user_logger")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(logging_path, "app.log"),
        when="midnight",
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _logger_instance = logger
    return _logger_instance


def get_logger() -> logging.Logger:
    """어디서든 이미 초기화된 로거를 가져올 때"""
    if _logger_instance is None:
        raise RuntimeError(
            "Logger가 초기화되지 않았습니다. init_logger()를 먼저 호출하세요."
        )
    return _logger_instance