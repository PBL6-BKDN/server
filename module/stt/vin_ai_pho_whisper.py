import torch
from transformers import pipeline
from module.stt import STT
from log import setup_logger

logger = setup_logger(__name__)

class VinAiPhoWhisper(STT):
    def __init__(self):
        super().__init__()
        self.transcriber = None
        # Khởi tạo model STT trên CPU
        try:
            device = torch.device("cpu")
            self.transcriber = pipeline(
                "automatic-speech-recognition", 
                model="vinai/PhoWhisper-base",  
                generate_kwargs={"language": "br", "task": "transcribe"},
                device=device,
                chunk_length_s=100
            )
            logger.info("Loaded PhoWhisper STT model on CPU successfully")
        except Exception as e:
            logger.error(f"Failed to load PhoWhisper STT model on CPU: {e}")

    def get_text_from_audio(self, audio_data, **kwargs):
        try:
            self.load_model()
            output = self.transcriber(inputs=kwargs.get("saved_file_path"))
            transcription = output.get('text', '')
            self.unload_model()
            return transcription
        
        except Exception as e:
            logger.error(f"Error in audio processing: {e}", exc_info=True)
            return "Lỗi hệ thống chuyển đổi âm thanh thành văn bản."
        
    def load_model(self):
        # Chuyển model lên GPU
        try:
            if self.transcriber is not None:
                self.transcriber.model = self.transcriber.model.to("cuda")
                self.transcriber.device = torch.device("cuda")
                logger.info("Moved PhoWhisper STT model to GPU successfully")
            else:
                logger.warning("No model loaded, cannot move to GPU")
        except Exception as e:
            logger.error(f"Failed to move PhoWhisper STT model to GPU: {e}")
            
    def unload_model(self):
        # Chuyển model về CPU trước khi unload
        try:
            if self.transcriber is not None:
                self.transcriber.model = self.transcriber.model.to("cpu")
                self.transcriber.device = torch.device("cpu")
                logger.info("Moved PhoWhisper STT model back to CPU successfully")
        except Exception as e:
            logger.error(f"Failed to move PhoWhisper STT model to CPU: {e}")
                
    def __del__(self):
        # Đảm bảo model được chuyển về CPU trước khi giải phóng bộ nhớ
        self.transcriber = None
        logger.info("Cleaned up PhoWhisper STT model successfully")