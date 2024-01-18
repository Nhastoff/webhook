from pydantic.v1 import BaseSettings


class Settings(BaseSettings):
    DJANGO_SETTINGS_MODULE: str
    DATABASE_URL: str
    DB_HOST: str
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    DJANGO_KEYCLOAK_INTERNAL_URL: str
    KEYCLOAK_CLIENT_SECRET: str
    SECRET_KEY: str

    class Config:
        env_file = ".env"


settings = Settings()
