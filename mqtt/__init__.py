"""
Blind Assist Device - MQTT Server
================================

This module implements the server component for the Blind Assist Device:
- Connects to MQTT broker to communicate with all devices
- Receives voice input and processes speech-to-text
- Sends text-to-speech responses back to devices
- Processes obstacle detection alerts
- Receives and stores device images
- Monitors device status and heartbeats

MQTT Topics:
- device/{deviceId}/stt/audio: Voice streaming from devices
- device/{deviceId}/obstacle: Obstacle detection alerts
- device/{deviceId}/info: Device status/heartbeat 
- device/{deviceId}/status: Online/offline status
- device/{deviceId}/ping: Ping requests from devices
- server/{deviceId}/tts: Text-to-speech to devices
- server/{deviceId}/command: Commands to devices
- server/{deviceId}/pong: Pong responses to devices
"""

# Export main server class
from mqtt.server import MQTTAgentServer


__all__ = ['MQTTAgentServer']
