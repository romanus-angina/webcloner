# backend/app/config.py

import os
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

class BrowserSettings:
    """Browser automation configuration settings."""
    
    # Browser Type
    BROWSER_TYPE: str = os.getenv("BROWSER_TYPE", "chromium")
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
    BROWSER_TIMEOUT: int = int(os.getenv("BROWSER_TIMEOUT", "30"))
    BROWSER_NAVIGATION_TIMEOUT: int = int(os.getenv("BROWSER_NAVIGATION_TIMEOUT", "30"))
    BROWSER_VIEWPORT_WIDTH: int = int(os.getenv("BROWSER_VIEWPORT_WIDTH", "1920"))
    BROWSER_VIEWPORT_HEIGHT: int = int(os.getenv("BROWSER_VIEWPORT_HEIGHT", "1080"))
    BROWSER_USER_AGENT: Optional[str] = os.getenv("BROWSER_USER_AGENT")
    MAX_BROWSER_INSTANCES: int = int(os.getenv("MAX_BROWSER_INSTANCES", "5"))
    BROWSER_POOL_SIZE: int = int(os.getenv("BROWSER_POOL_SIZE", "3"))
    BROWSER_MAX_RETRIES: int = int(os.getenv("BROWSER_MAX_RETRIES", "3"))
    BROWSER_RETRY_DELAY: int = int(os.getenv("BROWSER_RETRY_DELAY", "2"))
    BROWSER_DEBUG: bool = os.getenv("BROWSER_DEBUG", "false").lower() == "true"
    BROWSER_SLOW_MO: int = int(os.getenv("BROWSER_SLOW_MO", "0"))
    BROWSERBASE_API_KEY: Optional[str] = os.getenv("BROWSERBASE_API_KEY")
    BROWSERBASE_PROJECT_ID: Optional[str] = os.getenv("BROWSERBASE_PROJECT_ID")
    USE_CLOUD_BROWSER: bool = os.getenv("USE_CLOUD_BROWSER", "false").lower() == "true"


class Settings(BrowserSettings, BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application settings
    app_name: str = Field(default="Website Cloner")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    environment: str = Field(default="development")
    
    # Server settings
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    
    # CORS settings - Fixed for Pydantic v2
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from various formats."""
        if isinstance(v, str):
            # Handle comma-separated string
            if ',' in v:
                return [origin.strip() for origin in v.split(',')]
            # Handle single URL string
            elif v.startswith('http'):
                return [v]
            # Handle JSON string
            else:
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return [v]  # Fallback to single item list
        return v
    
    # API settings
    api_v1_prefix: str = Field(default="/api/v1")
    
    # External services
    anthropic_api_key: Optional[str] = Field(default=None)
    
    # Rate limiting
    rate_limit_requests: int = Field(default=10)
    rate_limit_window: int = Field(default=60)
    
    # File storage
    temp_storage_path: str = Field(default="./data")
    max_file_size: int = Field(default=10 * 1024 * 1024)  # 10MB
    
    # Scraping settings
    request_timeout: int = Field(default=30)
    max_retries: int = Field(default=3)
    user_agent: str = Field(
        default="Mozilla/5.0 (compatible; WebsiteCloner/1.0)"
    )
    
    # Redis settings (optional)
    redis_url: Optional[str] = Field(default=None)
    redis_password: Optional[str] = Field(default=None)
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"  # Ignore unknown environment variables
    }


# Global settings instance
settings = Settings()

# Create directories if they don't exist
os.makedirs(settings.temp_storage_path, exist_ok=True)
os.makedirs(f"{settings.temp_storage_path}/screenshots", exist_ok=True)
os.makedirs(f"{settings.temp_storage_path}/generated", exist_ok=True)
os.makedirs(f"{settings.temp_storage_path}/assets", exist_ok=True)