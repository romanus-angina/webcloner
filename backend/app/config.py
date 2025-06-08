import os
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application settings
    app_name: str = "Website Cloner"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # API settings
    api_v1_prefix: str = "/api/v1"
    
    # External services
    anthropic_api_key: Optional[str] = None
    
    # Rate limiting
    rate_limit_requests: int = 10
    rate_limit_window: int = 60
    
    # File storage
    temp_storage_path: str = "./data"
    max_file_size: int = 10 * 1024 * 1024

    # Scraping settings
    request_timeout: int = 30
    max_retries: int = 3
    
    # --- Browser & Stealth Settings ---
    BROWSER_TYPE: str = "chromium"
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30
    BROWSER_NAVIGATION_TIMEOUT: int = 30
    BROWSER_VIEWPORT_WIDTH: int = 1920
    BROWSER_VIEWPORT_HEIGHT: int = 1080
    BROWSER_USER_AGENT: Optional[str] = None
    MAX_BROWSER_INSTANCES: int = 5
    BROWSER_POOL_SIZE: int = 3
    BROWSER_MAX_RETRIES: int = 3
    BROWSER_RETRY_DELAY: int = 2
    BROWSER_DEBUG: bool = False
    BROWSER_SLOW_MO: int = 0
    USE_CLOUD_BROWSER: bool = False
    BROWSERBASE_API_KEY: Optional[str] = None
    BROWSERBASE_PROJECT_ID: Optional[str] = None
    USER_AGENTS: List[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/126.0",
    ]
    PROXY_URL: Optional[str] = None
    USE_STEALTH_PLUGIN: bool = True

settings = Settings()

os.makedirs(settings.temp_storage_path, exist_ok=True)
os.makedirs(f"{settings.temp_storage_path}/screenshots", exist_ok=True)
os.makedirs(f"{settings.temp_storage_path}/generated", exist_ok=True)
os.makedirs(f"{settings.temp_storage_path}/assets", exist_ok=True)
os.makedirs(f"{settings.temp_storage_path}/extractions", exist_ok=True)