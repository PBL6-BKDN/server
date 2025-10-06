"""
Helper functions for the MQTT server
"""
import os
import time

from log import setup_logger

logger = setup_logger(__name__)

def save_device_log(device_id, log_data):
    """
    Save device logs to a file

    Args:
        device_id (str): ID of the device
        log_data (dict): Log data including level, message, timestamp
    """
    try:
        # Đảm bảo thư mục logs tồn tại
        logs_dir = os.path.join(os.path.dirname(__file__), "../../device_logs")
        os.makedirs(logs_dir, exist_ok=True)

        # Tạo tên file dựa trên device_id
        log_file = os.path.join(logs_dir, f"{device_id}.log")

        # Format log message
        timestamp = log_data.get(
            "timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
        level = log_data.get("level", "INFO")
        message = log_data.get("message", "")
        log_line = f"[{timestamp}] [{level}] {message}\n"

        # Ghi vào file
        with open(log_file, "a") as f:
            f.write(log_line)
    except Exception as e:
        logger.error(f"Error saving device log: {e}")
