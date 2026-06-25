from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    api_key: str
    vllm_url: str = "http://vllm:8080/v1"
    model: str = "zai-org/GLM-OCR"
    max_pages: int = 50
    max_upload_bytes: int = 100 * 1024 * 1024
    max_concurrency: int = 1
    queue_max: int = 8
    scratch_dir: str = "/scratch"


@lru_cache
def get_settings() -> Settings:
    return Settings()
