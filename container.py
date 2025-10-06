"""
Service Container để quản lý dependencies một cách sạch sẽ
"""
from typing import Any, Dict, Optional
from log import setup_logger

logger = setup_logger(__name__)

class ServiceContainer:
    """Container để quản lý services"""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
    
    def register(self, name: str, service: Any):
        """Đăng ký service"""
        self._services[name] = service
        logger.debug(f"Đã đăng ký service: {name}")
    
    def get(self, name: str) -> Any:
        """Lấy service"""
        if name not in self._services:
            raise ValueError(f"Service '{name}' chưa được đăng ký")
        return self._services[name]
    
    def has(self, name: str) -> bool:
        """Kiểm tra service có tồn tại không"""
        return name in self._services

# Global container instance
container = ServiceContainer()