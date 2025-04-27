import os
from pydantic import BaseSettings, Field
from typing import Optional
from enum import Enum

class LLMProvider(str, Enum):
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file"""
    
    # LLM API settings
    LLM_API_KEY: Optional[str] = Field(None, description="API key for the LLM provider")
    LLM_PROVIDER: LLMProvider = Field(LLMProvider.GOOGLE, description="LLM provider to use")
    
    # Server settings
    DEBUG: bool = Field(True, description="Debug mode flag")
    PORT: int = Field(8000, description="Port to run the server on")
    HOST: str = Field("0.0.0.0", description="Host to bind the server to")
    
    # Game settings
    MAX_PLAYERS: int = Field(11, description="Maximum number of players allowed")
    MIN_PLAYERS: int = Field(5, description="Minimum number of players required")
    DEFAULT_PLAYER_COUNT: int = Field(7, description="Default number of players")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create a global settings instance
settings = Settings() 