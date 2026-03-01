import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    VLLM_COSMOS_URL: str = os.getenv('VLLM_COSMOS_API_URL')
    VLLM_TRANSLATE_URL: str = os.getenv('VLLM_TRANSLATE_API_URL')
    OLLAMA_API_URL: str = os.getenv('OLLAMA_API_URL')
    TEMP_DIR: Path = Path('/tmp/ai_api_temp')

    class Config:
        env_file = '.env'

settings = Settings()
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
