import os
from typing import Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application settings
    app_name: str = Field(default="Website Cloner", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # CORS settings
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        env="CORS_ORIGINS"
    )
    
    # API settings
    api_v1_prefix: str = Field(default="/api/v1", env="API_V1_PREFIX")
    
    # External services
    anthropic_api_key: str = Field(default=None, env="ANTHROPIC_API_KEY")
    
    # Rate limiting
    rate_limit_requests: int = Field(default=10, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, env="RATE_LIMIT_WINDOW")  # seconds
    
    # File storage
    temp_storage_path: str = Field(default="./data", env="TEMP_STORAGE_PATH")
    max_file_size: int = Field(default=10 * 1024 * 1024, env="MAX_FILE_SIZE")  # 10MB
    
    # Scraping settings
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    user_agent: str = Field(
        default="Mozilla/5.0 (compatible; WebsiteCloner/1.0)",
        env="USER_AGENT"
    )
    
    # Redis settings (for caching and rate limiting)
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Create directories if they don't exist
os.makedirs(settings.temp_storage_path, exist_ok=True)
os.makedirs(f"{settings.temp_storage_path}/screenshots", exist_ok=True)
os.makedirs(f"{settings.temp_storage_path}/generated", exist_ok=True)
os.makedirs(f"{settings.temp_storage_path}/assets", exist_ok=True)