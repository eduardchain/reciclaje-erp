from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    # Database
    DATABASE_URL: str = "postgresql://admin:admin@localhost:5432/reciclaje_db"

    # Security
    SECRET_KEY: str = "your-secret-key-change-this-in-production"

    # Debug
    DEBUG: bool = True

    # Project
    PROJECT_NAME: str = "ReciclaTrac API"
    VERSION: str = "0.1.0"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
