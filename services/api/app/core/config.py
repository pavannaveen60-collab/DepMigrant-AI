from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    # Nebius / NVIDIA
    nebius_api_key: Optional[str] = None
    nebius_base_url: str = "https://api.studio.nebius.com/v1"
    nebius_model: str = "nvidia/nemotron-3-ultra"
    
    # Alternative: NVIDIA NIM
    nvidia_nim_api_key: Optional[str] = None
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_nim_model: str = "nvidia/nemotron-3-ultra"
    
    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_workers: int = 1
    
    # Database
    database_url: str = f"sqlite:///{Path.home() / 'DepMigrant AI' / 'depmigrant.db'}"
    
    # Sandbox
    sandbox_timeout: int = 300
    sandbox_max_memory_mb: int = 2048
    sandbox_max_cpu_percent: int = 80
    allow_unsafe_repository_execution: bool = False
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = str(Path(__file__).resolve().parents[4] / ".env")
        case_sensitive = False

settings = Settings()