from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_streamlit_secrets() -> dict[str, Any]:
    try:
        import streamlit as st

        return _drop_blank_secret_values(dict(st.secrets))
    except Exception:
        return {}


def _drop_blank_secret_values(values: dict[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in values.items() if value not in ("", None)}


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    default_lookback_days: int = Field(default=90, alias="DEFAULT_LOOKBACK_DAYS")
    max_items_per_source: int = Field(default=50, alias="MAX_ITEMS_PER_SOURCE")
    candidate_items_per_source: int = Field(default=100, alias="CANDIDATE_ITEMS_PER_SOURCE")
    candidate_overfetch_multiplier: float = Field(default=2.0, alias="CANDIDATE_OVERFETCH_MULTIPLIER")
    candidate_overfetch_max: int = Field(default=2000, alias="CANDIDATE_OVERFETCH_MAX")

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")

    apify_api_key_1: str | None = Field(default=None, alias="APIFY_API_KEY_1")
    apify_api_key_2: str | None = Field(default=None, alias="APIFY_API_KEY_2")
    apify_api_key_3: str | None = Field(default=None, alias="APIFY_API_KEY_3")
    apify_api_key_4: str | None = Field(default=None, alias="APIFY_API_KEY_4")
    apify_api_token_1: str | None = Field(default=None, alias="APIFY_API_TOKEN_1")
    apify_api_token_2: str | None = Field(default=None, alias="APIFY_API_TOKEN_2")
    apify_api_token_3: str | None = Field(default=None, alias="APIFY_API_TOKEN_3")
    apify_api_token_4: str | None = Field(default=None, alias="APIFY_API_TOKEN_4")
    apify_key_0: str | None = Field(default=None, alias="APIFY_KEY_0")
    apify_key_1: str | None = Field(default=None, alias="APIFY_KEY_1")
    appify_key_0: str | None = Field(default=None, alias="APPIFY_KEY_0")
    appify_key_1: str | None = Field(default=None, alias="APPIFY_KEY_1")

    youtube_api_key: str | None = Field(default=None, alias="YOUTUBE_API_KEY")

    @property
    def apify_api_keys(self) -> list[str]:
        keys = [
            self.appify_key_0,
            self.appify_key_1,
            self.apify_key_0,
            self.apify_key_1,
            self.apify_api_key_1,
            self.apify_api_key_2,
            self.apify_api_key_3,
            self.apify_api_key_4,
            self.apify_api_token_1,
            self.apify_api_token_2,
            self.apify_api_token_3,
            self.apify_api_token_4,
        ]
        deduped: list[str] = []
        for key in keys:
            if key and key not in deduped:
                deduped.append(key)
        return deduped


@lru_cache
def get_settings() -> AppSettings:
    load_dotenv()
    streamlit_values = _load_streamlit_secrets()
    return AppSettings(**streamlit_values)
