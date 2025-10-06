"""
Main entry point for the agent-based server
"""
import asyncio
from mqtt.server import MQTTAgentServer
async def main():
    server = MQTTAgentServer()
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
