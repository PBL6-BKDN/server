"""
MQTT Client configuration and setup
"""
import json
import time
import uuid

import paho.mqtt.client as mqtt

import config
from log import setup_logger

logger = setup_logger(__name__)

class MQTTClient:
    def __init__(self, message_handlers=None):
        """
        Khởi tạo MQTT client với các handlers xử lý message
        
        Args:
            message_handlers (dict): Dictionary các handler theo topic pattern
        """
        self.server_id = f"server-{uuid.uuid4().hex[:8]}"
        self.client = mqtt.Client(
            client_id=self.server_id,
            clean_session=False,
            protocol=mqtt.MQTTv311,
            transport=config.BROKER_TRANSPORT
        )

        self.client.max_inflight_messages_set(0)  # 0 = không giới hạn, hoặc số lớn hơn 20
        
        # Lưu các message handlers
        self.message_handlers = message_handlers or {}
        
        # Cấu hình client
        self.client.username_pw_set(config.MQTT_USER, config.MQTT_PASS)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # Set last will message
        self.client.will_set(
            "server/status",
            json.dumps({
                "status": "offline",
                "serverId": self.server_id,
                "ts": int(time.time()*1000)
            }),
            qos=2,
            retain=True
        )
        
        # Cấu hình TLS và WebSocket nếu cần
        if config.BROKER_TRANSPORT == "websockets":
            self.client.ws_set_options(path=config.BROKER_WS_PATH)
        if config.BROKER_USE_TLS:
            self.client.tls_set()
    
    def connect(self):
        """
        Kết nối tới MQTT broker
        """
        try:
            logger.info("[SERVER] Đang kết nối đến MQTT broker...")
            self.client.connect(config.BROKER_HOST, config.BROKER_PORT, keepalive=60)
            logger.info("[SERVER] Kết nối thành công!")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Không thể kết nối đến MQTT broker: {e}")
            return False
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        """
        Callback khi kết nối MQTT được thiết lập
        """
        logger.info(f"Connected to MQTT broker with result code: {rc}")
        
        # Đăng ký nhận tất cả các thiết bị (wildcard +)
        client.subscribe("device/+/stt/audio", qos=1)  # Audio streams
        client.subscribe("device/+/obstacle", qos=1)   # Obstacle alerts
        client.subscribe("device/+/log", qos=2)        # Log messages
        client.subscribe("device/+/info", qos=2)       # Device info
        client.subscribe("device/+/status", qos=2)     # Online/offline status
        client.subscribe("device/+/ping", qos=2)       # Ping requests
        client.subscribe("device/+/mic", qos=1)        # Mic data
        
        # Thông báo server đã online
        client.publish("server/status",
            json.dumps({
                "status": "online",
                "serverId": self.server_id,
                "ts": int(time.time()*1000)
            }),
            qos=2,
            retain=True
        )
    
    def on_message(self, client, userdata, msg):
        """
        Callback khi nhận được message MQTT
        Định tuyến message tới handler phù hợp
        """
        try:
            payload = json.loads(msg.payload.decode())
            topic_parts = msg.topic.split("/")
            if msg.topic.endswith("audio"):
                logger.info(f"Received audio from {msg.topic}")
            else:
                logger.info(f"Received message from {msg.topic}: {payload}")
            
            if len(topic_parts) >= 3:
                device_id = topic_parts[1]
                topic_type = topic_parts[2]  # stt, obstacle, info, etc.
                
                # Nếu có topic cuối cùng (e.g., audio trong device/id/stt/audio)
                if len(topic_parts) >= 4:
                    subtopic = topic_parts[3]
                    handler_key = f"{topic_type}/{subtopic}"
                else:
                    handler_key = topic_type
                
                # # Tìm và gọi handler phù hợp
                # if handler_key in self.message_handlers:
                #     self.message_handlers[handler_key](self, device_id, payload)
                # elif topic_type in self.message_handlers:
                #     self.message_handlers[topic_type](self, device_id, payload)
                # else:
                #     logger.warning(f"No handler for topic: {msg.topic}")
                handler = self.message_handlers.get(handler_key) or self.message_handlers.get(topic_type)
                if handler:
                    try:
                        # Nếu handler sync (3 tham số, unbound) hoặc cần client:
                        handler(self, device_id, payload)
                    except TypeError:
                        # Trường hợp handler là bound method: không truyền self của MQTTClient
                        import asyncio, inspect
                        if inspect.iscoroutinefunction(handler):
                            try:
                                loop = asyncio.get_running_loop()
                                loop.create_task(handler(device_id, payload))
                            except RuntimeError:
                                asyncio.run(handler(device_id, payload))
                        else:
                            handler(device_id, payload)
                    
        except json.JSONDecodeError:
            logger.error(f"Malformed JSON in message: {msg.topic}")
        except Exception as e:
            logger.error(f"Error processing message from {msg.topic}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def publish(self, topic, payload, qos=1, retain=False):
        """
        Gửi message tới MQTT broker
        
        Args:
            topic (str): Topic để gửi
            payload (dict): Payload JSON
            qos (int): Quality of Service (0, 1, 2)
            retain (bool): Retain flag
        """
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        
        self.client.publish(topic, payload, qos=qos, retain=retain)
        
    def loop_forever(self):
        """
        Chạy vòng lặp MQTT vô hạn
        """
        self.client.loop_forever()
    
    def disconnect(self):
        """
        Ngắt kết nối từ MQTT broker
        """
        # Thông báo server offline
        self.client.publish("server/status",
            json.dumps({
                "status": "offline",
                "serverId": self.server_id,
                "ts": int(time.time()*1000)
            }),
            qos=2,
            retain=True
        )
        self.client.disconnect()
