from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    UPLOAD_DIR: str = "uploads/audio"
    MAX_FILE_SIZE_MB: int = 50
    
    class Config:
        env_file = Path(__file__).parent.parent.parent / ".env"
        extra = "allow"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
