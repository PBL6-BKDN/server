"""
Handler for audio processing with multi-agent system
"""
import asyncio
import base64
import os
import threading
import time
import numpy as np
import soundfile as sf
from transformers import pipeline

from log import setup_logger
from mcp_custom.service.tts import generate_tts
from module.stt.vin_ai_pho_whisper import VinAiPhoWhisper
from multi_agent_system import MultiAgentSystem
from config import LLM_API_KEY, LLM_MODEL, LLM_BASE_URL
from mqtt.client import MQTTClient

logger = setup_logger(__name__)

class AgentAudioHandler:
    def __init__(self, mqtt_client: MQTTClient, multi_agent_system: MultiAgentSystem):
        """
        Khởi tạo AgentAudioHandler với multi-agent system và STT model
        """
        # Dictionary để lưu trữ các audio chunks đang được nhận
        self.audio_stream_buffers = {}
        
        self.mqtt_client = mqtt_client
        
        # Khởi tạo multi-agent system
        self.multi_agent_system = multi_agent_system
       

        # Khởi tạo model STT
        self.transcriber = VinAiPhoWhisper()
        
        # Khởi tạo luồng cleanup
        self.cleanup_thread = None
        self.is_running = False
        
        # Queue cho text stream -> từng câu hoàn chỉnh
        self.text_stream_queues = {}
        # Task đang chạy tách câu và TTS theo device
        self.text_stream_tasks = {}
     

    def start_cleanup_thread(self):
        """ 
        Khởi động luồng dọn dẹp các audio buffer định kỳ
        """
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.is_running = True
            self.cleanup_thread = threading.Thread(target=self._cleanup_audio_buffers, daemon=True)
            self.cleanup_thread.start()
            logger.info("Audio buffer cleanup thread started")
    
    def stop_cleanup_thread(self):
        """
        Dừng luồng dọn dẹp audio buffer
        """
        self.is_running = False
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=1)
            logger.info("Audio buffer cleanup thread stopped")
    
    def _cleanup_audio_buffers(self):
        """
        Dọn dẹp các audio buffer đã quá hạn (không nhận đủ chunks)
        """
        while self.is_running:
            current_time = time.time()
            for stream_key in list(self.audio_stream_buffers.keys()):
                # Nếu buffer tồn tại quá 60s mà chưa nhận đủ chunks
                if current_time - self.audio_stream_buffers[stream_key]["timestamp"] > 60:
                    device_id, stream_id = stream_key.split("_", 1)
                    logger.warning(f"Audio stream {stream_id} from {device_id} timed out, cleaning up")
                    del self.audio_stream_buffers[stream_key]
            
            # Kiểm tra mỗi 30 giây
            time.sleep(30)

    def _get_text_queue(self, device_id: str):
        if device_id not in self.text_stream_queues:
            self.text_stream_queues[device_id] = asyncio.Queue()
        return self.text_stream_queues[device_id]

    async def _sentence_stream_worker(self, device_id: str):
        """
        Worker: nhận các chunk text, gom thành câu theo dấu câu (., !, ?, xuống dòng),
        khi đủ một câu thì generate TTS và gửi âm thanh về thiết bị.
        """
        queue = self._get_text_queue(device_id)
        buffer = ""
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    # tín hiệu kết thúc stream cho device
                    break
                buffer += chunk
                # Tìm câu hoàn chỉnh
                sentences = []
                start = 0
                for i, ch in enumerate(buffer):
                    if ch in ".!?\n":
                        sentences.append(buffer[start:i+1].strip())
                        start = i+1
                buffer = buffer[start:]

                for sent in sentences:
                    if not sent:
                        continue
                    try:
                        audio, fs = await generate_tts(sent)
                        self.send_audio_to_device(device_id, audio, format_audio="pcm16le", sample_rate=fs)
                    except Exception as e:
                        logger.error(f"TTS/send error for {device_id}: {e}")
        finally:
            # flush phần còn lại nếu có
            residual = buffer.strip()
            if residual:
                try:
                    audio, fs = await generate_tts(residual)
                    self.send_audio_to_device(device_id, audio, format_audio="pcm16le", sample_rate=fs)
                except Exception as e:
                    logger.error(f"Final TTS/send error for {device_id}: {e}")
            self.text_stream_tasks.pop(device_id, None)
            self.text_stream_queues.pop(device_id, None)
    
    def save_audio_file(self, audio_data, device_id, stream_id, format_audio, sample_rate):
        """
        Lưu dữ liệu âm thanh vào một file duy nhất, ghi đè nếu file đã tồn tại
        
        Args:
            audio_data: Dữ liệu âm thanh dạng bytes
            device_id: ID của thiết bị gửi âm thanh
            stream_id: ID của luồng âm thanh
            format_audio: Định dạng âm thanh (pcm16le, wav, etc.)
            sample_rate: Tần số lấy mẫu
            
        Returns:
            str: Đường dẫn đến file âm thanh đã lưu
        """
        try:
            # Tạo thư mục để lưu file âm thanh nếu chưa tồn tại
            audio_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "audio", "recordings")
            os.makedirs(audio_dir, exist_ok=True)
            
            # Sử dụng tên file cố định là "audio_recording" thay vì tạo tên file dựa trên timestamp
            file_name = "audio_recording"
            
            # Xác định định dạng file và lưu
            if format_audio == "pcm16le":
                # Nếu là PCM 16-bit, chuyển đổi thành numpy array và lưu dưới dạng WAV
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
                file_path = os.path.join(audio_dir, f"{file_name}.wav")
                sf.write(file_path, audio_np, sample_rate)
            else:
                # Nếu là định dạng khác, thử lưu trực tiếp
                file_path = os.path.join(audio_dir, f"{file_name}.{format_audio}")
                with open(file_path, 'wb') as f:
                    f.write(audio_data)
            
            logger.info(f"Saved audio file: {file_path}")
            return file_path
        
        except Exception as e:
            logger.error(f"Error saving audio file: {e}", exc_info=True)
            return None

    async def handle_stt_audio(self, device_id, payload):
        """
        Xử lý luồng âm thanh từ thiết bị, chuyển đổi thành văn bản và 
        sử dụng multi-agent system để xử lý yêu cầu
        """
        try:
            stream_id = payload.get("streamId")
            chunk_index = payload.get("chunkIndex", 0)
            total_chunks = payload.get("totalChunks", 1)
            is_last = payload.get("isLast", False)
            format_audio = payload.get("format", "pcm16le")
            sample_rate = payload.get("sampleRate", 16000)
            
            # Giải mã âm thanh từ base64
            audio_chunk = base64.b64decode(payload.get("data", ""))
            
            # Tạo key duy nhất cho stream này
            stream_key = f"{device_id}_{stream_id}"
            
            # Khởi tạo buffer cho stream nếu chưa tồn tại
            if stream_key not in self.audio_stream_buffers:
                self.audio_stream_buffers[stream_key] = {
                    "chunks": {},
                    "total_chunks": total_chunks,
                    "received_chunks": 0,
                    "format": format_audio,
                    "sample_rate": sample_rate,
                    "timestamp": time.time()
                }
            
            # Lưu chunk vào buffer
            self.audio_stream_buffers[stream_key]["chunks"][chunk_index] = audio_chunk
            self.audio_stream_buffers[stream_key]["received_chunks"] += 1
            
            logger.debug(f"Received audio chunk {chunk_index+1}/{total_chunks} from {device_id} (stream: {stream_id})")
            
            # Kiểm tra xem đã nhận đủ chunks chưa
            if is_last or self.audio_stream_buffers[stream_key]["received_chunks"] >= total_chunks:
                logger.info(f"Completed audio stream {stream_id} from {device_id}, processing...")
                
                # Kết hợp các chunks theo thứ tự
                all_chunks = []
                for i in range(total_chunks):
                    if i in self.audio_stream_buffers[stream_key]["chunks"]:
                        all_chunks.append(self.audio_stream_buffers[stream_key]["chunks"][i])
                    else:
                        logger.warning(f"Missing chunk {i} in stream {stream_id} from {device_id}")
                
                # Kết hợp tất cả chunks
                combined_audio = b''.join(all_chunks)
                
                # Lưu file âm thanh
                saved_file_path = self.save_audio_file(
                    combined_audio, 
                    device_id, 
                    stream_id, 
                    self.audio_stream_buffers[stream_key]["format"],
                    self.audio_stream_buffers[stream_key]["sample_rate"]
                )
                
                # Xử lý âm thanh thành text
                transcription = self.transcriber.get_text_from_audio(combined_audio, saved_file_path=saved_file_path)
                
                if transcription:
                    logger.info(f"Transcription from {device_id}: '{transcription}'")
                    
                    # Nếu muốn stream theo câu: dùng stream_final_answer
                    if self.multi_agent_system:
                        # Khởi động worker nếu chưa có
                        if device_id not in self.text_stream_tasks:
                            task = asyncio.create_task(self._sentence_stream_worker(device_id))
                            self.text_stream_tasks[device_id] = task

                        queue = self._get_text_queue(device_id)
                        async for chunk in self.multi_agent_system.process_audio_request(transcription, device_id):
                            await queue.put(chunk)

                        # Kết thúc stream cho device
                        await queue.put(None)
                    else:
                        # Fallback nếu không khởi tạo được agent
                        self.send_tts_response(device_id, f"Tôi đã nhận được: {transcription}, nhưng hệ thống xử lý chưa sẵn sàng.")
                
                # Xóa buffer sau khi xử lý xong
                del self.audio_stream_buffers[stream_key]
                
        except Exception as e:
            logger.error(f"Error processing audio from {device_id}: {e}", exc_info=True)

    def send_tts_response(self, device_id, text):
        """
        Gửi phản hồi text-to-speech đến thiết bị
        """
        payload = {
            "debugText": text,
            "ts": int(time.time()*1000)
        }

        self.mqtt_client.publish(f"server/{device_id}/audio", payload, qos=1)
        logger.info(f"Sent TTS to {device_id}: '{text}'")

    def send_audio_to_device(self, device_id, audio_data, format_audio="pcm16le", sample_rate=16000):
        """
        Gửi dữ liệu âm thanh từ server đến thiết bị
        
        Args:
            device_id: ID của thiết bị nhận âm thanh
            audio_data: Dữ liệu âm thanh dạng bytes
            format_audio: Định dạng âm thanh (mặc định: pcm16le)
            sample_rate: Tần số lấy mẫu (mặc định: 16000)
        """  
        try:
            stream_id = f"server_{int(time.time() * 1000)}"
            chunk_size = 1024 * 8  # 8KB chunks
            total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size
            
            logger.info(f"Sending audio to device {device_id}, total chunks: {total_chunks}, total size: {len(audio_data)} bytes")
            
            # Chia và gửi từng chunk
            for i in range(total_chunks):
                start = i * chunk_size
                end = min(start + chunk_size, len(audio_data))
                chunk_data = audio_data[start:end]
                
                # Tạo payload
                payload = {
                    "serverStreamId": stream_id,
                    "chunkIndex": i,
                    "totalChunks": total_chunks,
                    "isLast": (i == total_chunks - 1),
                    "timestamp": int(time.time() * 1000),
                    "format": format_audio,
                    "sampleRate": sample_rate,
                    "data": base64.b64encode(chunk_data).decode()
                }
                
                # Gửi đến topic dành cho audio từ server đến thiết bị với QoS=1
                self.mqtt_client.publish(f"server/{device_id}/audio", payload, qos=1)
                
                # Thêm delay nhỏ giữa các gói tin
                delay = min(0.05, 1.0 / total_chunks)
                time.sleep(delay)
            
            logger.info(f"Successfully sent {total_chunks} audio chunks to device {device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending audio to device {device_id}: {e}", exc_info=True)
            return False



