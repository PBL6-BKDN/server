"""
Main server class with multi-agent system
"""
import asyncio
import sys
import threading
import time

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, DEVICE_ID
from log import setup_logger
from mqtt.client import MQTTClient
from mqtt.handlers.audio import AgentAudioHandler
from mqtt.handlers.device import AgentDeviceHandler
from mqtt.handlers.obstacle import ObstacleHandler
from multi_agent_system import MultiAgentSystem
from container import container

logger = setup_logger(__name__)

class MQTTAgentServer:
    def __init__(self):
        """
        Khởi tạo server MQTT với hệ thống multi-agent
        """
        self.multi_agent_system = MultiAgentSystem(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,    
            model=LLM_MODEL
        )
        
        # Tạo placeholder cho agent_audio_handler (sẽ khởi tạo sau)
        self.agent_audio_handler = None
        self.agent_device_handler = None
        
        # Thiết lập các handler cho các topic sau khi đã khởi tạo handlers
        self.message_handlers = {
            "mic": self.handle_stt_audio_async,
            "stt/audio": self.handle_stt_audio_async,
            # "command": self.handle_command_async,
            # "info": self.device_handler.handle_device_info,
            # "status": self.device_handler.handle_device_status,
            # "ping": self.device_handler.handle_ping,
            # "obstacle": self.obstacle_handler.handle_obstacle,
        }
        
        # Khởi tạo MQTT client với message_handlers
        self.client = MQTTClient(message_handlers=self.message_handlers)
        
        # Khởi tạo agent_audio_handler sau khi có client
        self.agent_audio_handler = AgentAudioHandler(self.client, self.multi_agent_system)

        # Khởi tạo agent_device_handler sau khi có client
        self.agent_device_handler = AgentDeviceHandler(self.client)

        container.register("mqtt_client", self.client)
        container.register("device_handler", self.agent_device_handler)
        container.register("device_id", DEVICE_ID)
        
        # Event loop cho asyncio
        self.loop = asyncio.new_event_loop()
        
    def handle_stt_audio_async(self, device_id, payload):
        """
        Wrapper để gọi hàm async handle_stt_audio từ non-async context
        """
        if self.agent_audio_handler is not None:
            asyncio.run_coroutine_threadsafe(
                self.agent_audio_handler.handle_stt_audio(device_id, payload),
                self.loop
            )
        else:
            logger.warning("Agent audio handler chưa được khởi tạo")
    
    async def initialize_async(self):
        """
        Khởi tạo các thành phần async
        """
        # Khởi tạo hệ thống multi-agent
        await self.multi_agent_system.initialize_all()

        # Khởi động thread dọn dẹp audio buffer
        if self.agent_audio_handler is not None:
            self.agent_audio_handler.start_cleanup_thread()
        else:
            logger.warning("Agent audio handler chưa được khởi tạo")
    
    async def cleanup_async(self):
        """
        Dọn dẹp các tài nguyên async
        """
        # Dừng thread dọn dẹp audio buffer
        if self.agent_audio_handler is not None:
            self.agent_audio_handler.stop_cleanup_thread()
        
        # Dọn dẹp hệ thống multi-agent
        await self.multi_agent_system.cleanup_all()
    
    def run_async_loop(self):
        """
        Chạy event loop asyncio trong thread riêng
        """
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    async def start(self):
        """
        Khởi động server
        """
        logger.info("=" * 60)
        logger.info("    PBL6 Blind Assist - MQTT Agent Server    ")
        logger.info("=" * 60)
        
        # Khởi động thread cho event loop asyncio
        threading.Thread(target=self.run_async_loop, daemon=True).start()
        
        # Khởi tạo các thành phần async
        asyncio.run_coroutine_threadsafe(self.initialize_async(), self.loop)
        
        # Kết nối đến MQTT broker
        if not self.client.connect():
            sys.exit(1)
        
        # Khởi động thread kiểm tra trạng thái thiết bị
        # self.device_handler.start_status_check_thread()
        
        logger.info(f"[SERVER] Server đã khởi động với ID: {self.client.server_id}")
        logger.info("[SERVER] Đang lắng nghe các thiết bị...")
        logger.info("[SERVER] Nhấn Ctrl+C để thoát")
        
        # Chạy vòng lặp MQTT trong luồng chính
        try:
            self.client.loop_forever()
        except KeyboardInterrupt:
            await self.clean_up()
            
    async def clean_up(self):
        logger.info("\n[SERVER] Đang tắt server...")
            
        # Dừng các thread
        self.device_handler.stop_status_check_thread()
        
        # Dọn dẹp các tài nguyên async
        future = asyncio.run_coroutine_threadsafe(self.cleanup_async(), self.loop)
        future.result(timeout=5)  # Đợi tối đa 5 giây
        
        # Dừng event loop
        self.loop.call_soon_threadsafe(self.loop.stop)
        
        # Ngắt kết nối MQTT
        self.client.disconnect()
        
        logger.info("[SERVER] Đã tắt server MQTT")
        sys.exit(0)
            

       