import logging
from datetime import datetime


def get_userlogger(logging_path= '/usr/share/d_ollama/data/log/user') : 
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger
    
    now = datetime.now()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(f'{logging_path}/{now.date()}.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger
