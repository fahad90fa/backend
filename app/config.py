from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "CyberScholar AI"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    GOOGLE_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    
    DATABASE_URL: str = "sqlite:///./cyber_scholar.db"
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024
    
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    ADMIN_PASSWORD: str = ""
    
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8080,https://cyber-scholar-ai.vercel.app"
    ENVIRONMENT: str = "development"
    
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD_SECONDS: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings():
    settings = Settings()
    if not settings.ADMIN_PASSWORD:
        raise ValueError("ADMIN_PASSWORD environment variable must be set")
    return settings
