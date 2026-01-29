"""Configuration management for Listener component."""
from pydantic_settings import BaseSettings
from typing import Optional
import uuid


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Processing API
    processing_url: str = "http://processing:8000"
    listener_api_key: str

    # Listener identification
    listener_id: uuid.UUID
    listener_name: str = "Meshcore Listener"
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None

    # Device configuration
    device_path: str = "/dev/ttyUSB0"
    device_baud_rate: int = 115200

    # Polling configuration
    poll_interval_seconds: int = 30

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
