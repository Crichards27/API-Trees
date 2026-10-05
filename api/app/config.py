from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://game:gamepassword@db:5432/game"
    )

    redis_url: str = "redis://redis:6379/0"

    admin_token: str = "thats-a-my-wife"


settings = Settings()