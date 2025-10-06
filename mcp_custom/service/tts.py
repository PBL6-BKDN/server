import asyncio
import os
import httpx
import sys
import soundfile as sf

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import BASE_DIR, TTS_VOICE, TTS_SPEED
from log import setup_logger

logger = setup_logger(__name__)
    
async def generate_tts(text: str, file_name: str=None) -> tuple[bytes, int]:
    logger.info(f"Generating TTS for {text}")
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "http://localhost:8298/v1/audio/speech",
            headers={"Authorization": "Bearer viet-tts", "Content-Type": "application/json"},
            json={"model": "tts-1", "input": text, "voice": TTS_VOICE, "speed": TTS_SPEED}, timeout=300 # 5 minutes
        )
        res.raise_for_status()
        audio_bytes = res.content
        content_type = res.headers.get("Content-Type", "").split(";")[0].strip()

    ext_map = {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/ogg": ".ogg",
        "audio/flac": ".flac",
        "audio/x-flac": ".flac",
    }
    file_ext = ext_map.get(content_type, ".mp3")

    output_path = os.path.join(BASE_DIR, "debug",f"{file_name if file_name else "tts_test"}{file_ext}")

    def write_file(path: str, data: bytes):
        with open(path, "wb") as f:
            f.write(data)
            
        _, fs = sf.read(path)
        return int(fs)
    fs = write_file(output_path, audio_bytes)
    # await asyncio.to_thread(write_file, output_path, audio_bytes)
    logger.info(f"Saved TTS to: {output_path} with sample rate: {fs}")
    return audio_bytes, fs
    
async def main():
    tasks = [
        generate_tts("Xin chào! Tôi là trợ lý ảo của bạn.", "hello"),
        generate_tts("Dừng lại! Phía trước có vật cản!", "stop"),
        generate_tts("Trợ lý của bạn đã nhận được yêu cầu, chúng tôi đang xử lý.", "processing"),
    ]
    return await asyncio.gather(*tasks)

if __name__ == "__main__":
    
    saved_path = asyncio.run(main())
    print(saved_path)