from __future__ import annotations
import os
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    stt_provider: str = Field(default=os.getenv("STT_PROVIDER","whisper"))
    tts_provider: str = Field(default=os.getenv("TTS_PROVIDER","mms"))

    ollama_base_url: str = Field(default=os.getenv("OLLAMA_BASE_URL","http://127.0.0.1:11434"))
    ollama_chat_model: str = Field(default=os.getenv("OLLAMA_CHAT_MODEL","llama3.1:8b"))

    ollama_num_ctx: int = Field(default=int(os.getenv("OLLAMA_NUM_CTX","2048")))
    ollama_num_predict: int = Field(default=int(os.getenv("OLLAMA_NUM_PREDICT","384")))
    ollama_temperature: float = Field(default=float(os.getenv("OLLAMA_TEMPERATURE","0.1")))
    ollama_top_p: float = Field(default=float(os.getenv("OLLAMA_TOP_P","0.9")))
    ollama_repeat_penalty: float = Field(default=float(os.getenv("OLLAMA_REPEAT_PENALTY","1.12")))

    llm_provider: str = Field(default=os.getenv("LLM_PROVIDER",""))
    groq_api_key: str = Field(default=os.getenv("GROQ_API_KEY",""))
    groq_model: str = Field(default=os.getenv("GROQ_MODEL","llama-3.1-8b-instant"))
    groq_base_url: str = Field(default=os.getenv("GROQ_BASE_URL","https://api.groq.com/openai/v1"))

    whisper_model: str = Field(default=os.getenv("WHISPER_MODEL","medium"))
    whisper_device: str = Field(default=os.getenv("WHISPER_DEVICE","cpu"))
    whisper_compute_type: str = Field(default=os.getenv("WHISPER_COMPUTE_TYPE","int8"))

    torch_num_threads: int = Field(default=int(os.getenv("TORCH_NUM_THREADS","4")))
    torch_num_interop_threads: int = Field(default=int(os.getenv("TORCH_NUM_INTEROP_THREADS","2")))

    sqlite_path: str = Field(default=os.getenv("SQLITE_PATH","./data/app.db"))
    log_level: str = Field(default=os.getenv("LOG_LEVEL","INFO"))

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

try:
    import torch  # type: ignore
    torch.set_num_threads(settings.torch_num_threads)
    torch.set_num_interop_threads(settings.torch_num_interop_threads)
except Exception:
    pass
