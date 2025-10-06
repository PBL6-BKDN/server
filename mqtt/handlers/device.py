"""
Handlers for device status, information and ping
"""
import json
import time
from datetime import datetime

from log import setup_logger
from mqtt.utils.contacts import Contact
from mqtt.client import MQTTClient

logger = setup_logger(__name__)

class AgentDeviceHandler:
    def __init__(self, mqtt_client: MQTTClient ):
        """
        Khởi tạo DeviceHandler với các resources và trạng thái cần thiết
        """
        # Theo dõi trạng thái thiết bị
        self.connected_devices = {}

        self.status_thread = None
        self.is_running = False
        
        self.mqtt_client = mqtt_client
        
    def handle_device_info(self, mqtt_client, device_id, payload):
        """
        Xử lý thông tin thiết bị
        """
        battery = payload.get("battery")
        gps = payload.get("gps")

        logger.info(f"Device {device_id} info: Battery={battery*100:.1f}%")

        # Lưu trữ thông tin thiết bị
        if device_id not in self.connected_devices:
            self.connected_devices[device_id] = {}
        
        self.connected_devices[device_id]["battery"] = battery
        self.connected_devices[device_id]["gps"] = gps
        self.connected_devices[device_id]["last_seen"] = time.time()
        self.connected_devices[device_id]["status"] = "online"

    def handle_device_status(self, mqtt_client, device_id, payload):
        """
        Xử lý thay đổi trạng thái thiết bị (online/offline)
        """
        status = payload.get("status")
        
        if device_id not in self.connected_devices:
            self.connected_devices[device_id] = {}
        
        self.connected_devices[device_id]["status"] = status
        logger.info(f"Device {device_id} is now {status}")

        # Gửi thông báo nếu thiết bị offline
        if status == "offline":
            # TODO: Thông báo cho hệ thống giám sát
            pass

    def handle_ping(self, mqtt_client, device_id, payload):
        """
        Xử lý ping từ thiết bị và gửi pong response
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        logger.debug(f"[{current_time}] [{device_id}] [PING] {payload.get('data', '')}")
        
        # Gửi pong response về cho device
        response = {
            "data": "pong",
            "ts": int(time.time()*1000)
        }
        mqtt_client.publish(f"server/{device_id}/pong", response, qos=2)
        
        # Cập nhật trạng thái thiết bị
        if device_id not in self.connected_devices:
            self.connected_devices[device_id] = {}
            logger.info(f"[NEW] Thiết bị mới kết nối: {device_id}")
            
        # Cập nhật thời gian thấy thiết bị gần nhất
        self.connected_devices[device_id]["last_ping"] = time.time()
        self.connected_devices[device_id]["last_seen"] = time.time()
        self.connected_devices[device_id]["status"] = "online"
        
        # In ra danh sách các thiết bị đang hoạt động nếu là ping đầu tiên
        if "first_ping" not in self.connected_devices[device_id]:
            self.connected_devices[device_id]["first_ping"] = True
            active_devices = [d for d, info in self.connected_devices.items() 
                              if info.get("status") == "online"]
            logger.info(f"[SERVER] Hiện có {len(active_devices)} thiết bị đang kết nối: {', '.join(active_devices)}")

    def handle_command(self, mqtt_client, device_id, command, params=None):
        """
        Xử lý lệnh từ thiết bị
        """
        if command == "send_sms":
            contact_name = params.get("name") 
            phone_number = params.get("phone_number")
            if not phone_number and contact_name:
                phone_number = Contact.get_phone_by_name(contact_name)
            if not phone_number:
                logger.error("send_sms: Không tìm thấy số điện thoại từ tên liên hệ và không có 'phone_number' cung cấp")
                return
            self.send_command(mqtt_client, device_id, command, params)
        elif command == "capture":
            pass
        
    def send_command(self, mqtt_client, device_id, command, params=None):
        """
        Gửi lệnh đến thiết bị
        """
        timestamp_ms = int(time.time()*1000)
        params = params or {}

        if command == "send_sms":
            # Kỳ vọng params: {"name": "Tên trong danh bạ"} hoặc {"phone_number": "+84..."}
            # Ưu tiên lấy số từ tên trong danh bạ nếu có
            contact_name = params.get("name") or params.get("contact_name")
            phone_number = params.get("phone_number")
            if not phone_number and contact_name:
                phone_number = Contact.get_phone_by_name(contact_name)
            if not phone_number:
                logger.error("send_sms: Không tìm thấy số điện thoại từ tên liên hệ và không có 'phone_number' cung cấp")
                return
            payload = {
                "command": command,
                "phone_number": phone_number,
                "message": params.get("message"),
                "ts": timestamp_ms,
            }
        elif command == "capture":
            # Kỳ vọng params: {"mode": "photo|video", "quality": "low|med|high"}
            payload = {
                "command": command,
                "mode": params.get("mode", "photo"),
                "quality": params.get("quality", "high"),
                "ts": timestamp_ms,
            }
        else:
            payload = {
                "command": command,
                "ts": timestamp_ms,
            }
        mqtt_client.publish(f"server/{device_id}/command", payload, qos=1)
        logger.info(f"Sent command '{command}' to {device_id}")

    def start_status_check_thread(self):
        """
        Bắt đầu luồng kiểm tra trạng thái thiết bị định kỳ
        """
        if self.status_thread is None or not self.status_thread.is_alive():
            import threading
            self.is_running = True
            self.status_thread = threading.Thread(target=self._status_loop, daemon=True)
            self.status_thread.start()
            logger.info("Device status check thread started")
    
    def stop_status_check_thread(self):
        """
        Dừng luồng kiểm tra trạng thái
        """
        self.is_running = False
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=1)
            logger.info("Device status check thread stopped")
        
    def _status_loop(self):
        """
        Vòng lặp kiểm tra trạng thái thiết bị định kỳ
        """
        while self.is_running:
            if not self.mqtt_client:
                time.sleep(5)
                continue
                
            current_time = time.time()
            for device_id, info in list(self.connected_devices.items()):
                # Nếu không có key last_seen, bỏ qua
                if "last_seen" not in info:
                    continue
    
                # Nếu thiết bị không gửi tin nhắn trong 15 giây
                if current_time - info["last_seen"] > 15 and info.get("status") != "offline":
                    logger.warning(f"[SERVER] Thiết bị {device_id} không phản hồi (> 15s)")
                    self.connected_devices[device_id]["status"] = "timeout"
    
                # Nếu thiết bị không gửi tin nhắn trong 60 giây, đánh dấu offline
                if current_time - info["last_seen"] > 60 and info.get("status") != "offline":
                    logger.warning(f"[SERVER] Thiết bị {device_id} đã ngắt kết nối (> 60s)")
                    self.connected_devices[device_id]["status"] = "offline"
                    
                    # Thông báo thiết bị offline
                    if self.mqtt_client:
                        self.mqtt_client.publish(f"device/{device_id}/status", {
                            "deviceId": device_id,
                            "status": "offline",
                            "reason": "ping_timeout",
                            "ts": int(current_time*1000)
                        }, qos=2, retain=True)
    
            # In danh sách thiết bị đang hoạt động mỗi 60 giây
            if int(current_time) % 60 == 0:
                active_devices = [d for d, info in self.connected_devices.items()
                                if info.get("status") not in ["offline", "timeout"]]
                if active_devices:
                    logger.info(f"[SERVER] {len(active_devices)} thiết bị đang hoạt động: {', '.join(active_devices)}")
    
            # Kiểm tra mỗi 5 giây
            time.sleep(5)