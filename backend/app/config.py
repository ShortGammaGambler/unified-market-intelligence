from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Unified Market Intelligence"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Databento
    DATABENTO_API_KEY: str = ""
    DATABENTO_LIVE_URL: str = "wss://live.databento.com/v0"
    DATABENTO_HIST_URL: str = "https://hist.databento.com/v0"
    DATABENTO_DATASET: str = "GLBX.MDP3"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/axiom"

    # Risk Parameters
    MAX_DRAWDOWN_LIMIT: float = 0.15
    MAX_POSITION_SIZE: float = 0.25
    MAX_LEVERAGE: float = 2.0
    AUTO_HALT_ENABLED: bool = True

    # Execution
    FIX_HOST: str = "localhost"
    FIX_PORT: int = 9876
    FIX_TARGET_COMP_ID: str = "AXIOM"
    FIX_SENDER_COMP_ID: str = "AXIOM_CLIENT"

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
