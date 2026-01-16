from __future__ import annotations

import os
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Runtime configuration loaded from .env / environment.

    Keep this minimal for the demo; optional providers remain available but non-required.
    """

    # --- Providers ---
    stt_provider: str = Field(default="whisper")
    tts_provider: str = Field(default="mms")

    # --- Optional LLM brain ---
    # If not set, the agent should fall back to rule-based logic.
    llm_provider: str = Field(default="")  # "ollama" | "groq" | "" (disabled)

    # Ollama (optional)
    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    ollama_chat_model: str = Field(default="llama3.2:3b")

    # Tunables for Ollama (optional; safe defaults)
    ollama_num_ctx: int = Field(default=2048)
    ollama_num_predict: int = Field(default=384)
    ollama_temperature: float = Field(default=0.1)
    ollama_top_p: float = Field(default=0.9)
    ollama_repeat_penalty: float = Field(default=1.12)

    # Groq (optional)
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.1-8b-instant")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")

    # Generic LLM timeout (used by Groq helper too)
    llm_timeout_seconds: int = Field(default=30)

    # --- Whisper STT ---
    whisper_model: str = Field(default="medium")
    whisper_device: str = Field(default="cpu")
    whisper_compute_type: str = Field(default="int8")

    # --- Performance (Mac-friendly) ---
    torch_num_threads: int = Field(default=4)
    torch_num_interop_threads: int = Field(default=2)

    # --- Storage ---
    sqlite_path: str = Field(default="./data/app.db")

    # --- Logging ---
    log_level: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Apply torch thread limits if torch is present
try:
    import torch  # type: ignore

    torch.set_num_threads(int(settings.torch_num_threads))
    torch.set_num_interop_threads(int(settings.torch_num_interop_threads))
except Exception:
    pass

# Make sure ffmpeg is found when running from GUI shells (optional quality-of-life)
# If you don't need it, you can delete this block.
try:
    if os.getenv("PATH") and "/opt/homebrew/bin" not in os.getenv("PATH", ""):
        os.environ["PATH"] = os.environ["PATH"] + ":/opt/homebrew/bin"
except Exception:
    pass
