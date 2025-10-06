import logging
from logging.handlers import RotatingFileHandler

RESET = "\x1b[0m"
COLORS = {
    "DEBUG": "\x1b[36m",    # Cyan
    "INFO": "\x1b[32m",     # Green
    "WARNING": "\x1b[33m",  # Yellow
    "ERROR": "\x1b[31m",    # Red
    "CRITICAL": "\x1b[41m", # Red background
}

class ColorFormatter(logging.Formatter):
    def format(self, record):
        log_color = COLORS.get(record.levelname, RESET)
        message = super().format(record)
        return f"{log_color}{message}{RESET}"

def setup_logger(name: str = __name__, level=logging.DEBUG):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Ngăn log record truyền lên logger cha gây ghi trùng
    logger.propagate = False

    # Kiểm tra xem logger đã có handler nào chưa, nếu có, không thêm handler mới
    if logger.hasHandlers():
        return logger

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)

    # File handler (max 1MB, không giữ backup)
    fh = RotatingFileHandler(
        "app.log", maxBytes=512, backupCount=0, encoding="utf-8"
    )
    fh.setLevel(level)

    # Formatter cho console (có màu)
    console_formatter = ColorFormatter(
        fmt="[%(filename)s:%(funcName)s:%(lineno)d] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch.setFormatter(console_formatter)

    # Formatter cho file (không màu)
    file_formatter = logging.Formatter(
        fmt="[%(filename)s:%(funcName)s:%(lineno)d] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(file_formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)

    return logger