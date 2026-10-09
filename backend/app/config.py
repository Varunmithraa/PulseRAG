import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "PulseRAG: Autonomous Agentic RAG Platform"
    PROJECT_VERSION: str = "1.0.0"
    
    # Google Gemini Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gemini-3.8-flash")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
    
    # Storage Paths
    SQLITE_PATH: Path = DATA_DIR / "pulserag_memory.db"
    CHROMA_PERSIST_DIR: Path = DATA_DIR / "chroma_db"
    
    # Real-Time Buffer Settings
    LIVE_BUFFER_MAX_SIZE: int = 500
    TIME_DECAY_LAMBDA: float = 0.05  # Decay rate per hour
    SEMANTIC_WEIGHT: float = 0.65    # Alpha: weight for similarity vs recency
    RECENCY_WEIGHT: float = 0.35     # 1 - Alpha: weight for recency score
    
    # Server Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True

    class Config:
        arbitrary_types_allowed = True

settings = Settings()
