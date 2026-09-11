from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

BASE_DIR = Path(__file__).parent.parent


class AuthJWT(BaseModel):
    private_key_path: Path = BASE_DIR / "api_v1" / "auth" / "certs" / "jwt-private.pem"
    public_key_path: Path = BASE_DIR / "api_v1" / "auth" / "certs" / "jwt-public.pem"
    algorithm: str = "RS256"
    access_token_expire_minutes: int = Field(default=15, gt=0)
    refresh_token_expire_days: int = Field(default=30, gt=0)


class Settings(BaseSettings):
    auth_jwt: AuthJWT = AuthJWT()

    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return URL.create(
            "postgresql+asyncpg", username=self.postgres_user,
            password=self.postgres_password, host=self.postgres_host,
            port=self.postgres_port, database=self.postgres_db,
        ).render_as_string(hide_password=False)


    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_nested_delimiter="__")


settings = Settings()
