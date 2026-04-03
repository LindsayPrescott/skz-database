from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    local_database_url: str | None = None  # Used when running scripts locally against Docker
    spotify_client_id: str
    spotify_client_secret: str

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
