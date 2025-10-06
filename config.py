import os
import dotenv

dotenv.load_dotenv()

ZMQ_URL = os.getenv("ZMQ_URL")
# Hostname Cloudflare Tunnel cho WebSocket
BROKER_HOST = os.getenv("BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
BROKER_TRANSPORT = os.getenv("BROKER_TRANSPORT", "tcp")
BROKER_USE_TLS = os.getenv("BROKER_USE_TLS", "False").lower() == "true"
BROKER_WS_PATH = os.getenv("BROKER_WS_PATH", "/")
DEVICE_ID = os.getenv("DEVICE_ID", "device001")
# Sử dụng tài khoản admin để có đầy đủ quyền
MQTT_USER = os.getenv("MQTT_USER", "admin")
MQTT_PASS = os.getenv("MQTT_PASS", "admin")

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")

# Weather API
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
# TomTom API
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")
# SerpAPI API Key
SERP_API_KEY = os.getenv("SERP_API_KEY")

AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
AUDIO_CHUNK_MS = int(os.getenv("AUDIO_CHUNK_MS", "500"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TTS_VOICE = "nu-nhe-nhang"
TTS_SPEED = 1.0