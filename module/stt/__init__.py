from transformers import pipeline
from log import setup_logger

logger = setup_logger(__name__)

class STT:
    def __init__(self):
        self.model = None
        self.processor = None
        
    def get_text_from_audio(self, audio_data, **kwargs) -> str:
        raise NotImplementedError("Subclass must implement this method")
    
    def load_model(self):
        raise NotImplementedError("Subclass must implement this method")
    
    def unload_model(self):
        raise NotImplementedError("Subclass must implement this method")
    
    def __del__(self):
        self.unload_model() 
        