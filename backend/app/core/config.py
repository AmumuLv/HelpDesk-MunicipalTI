"""Configuracion de la aplicacion (solo variables de entorno).

Regla del proyecto: ningun secreto se escribe en el codigo. Todo llega por
entorno con valores por defecto sensatos para desarrollo.
"""

from __future__ import annotations

import functools
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR.parent / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Aplicacion ────────────────────────────────────────────
    app_name: str = "Mesa de Ayuda TI"
    app_env: Literal["development", "production", "test"] = "development"
    api_prefix: str = "/api"
    log_level: str = "INFO"
    # Lista separada por comas en el entorno: NoDecode evita que pydantic intente JSON
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost",
            "http://localhost:5173",
            "http://localhost:8080",
        ]
    )

    # ── Negocio ───────────────────────────────────────────────
    business_timezone: str = "America/Lima"
    institution_name: str = "Municipalidad"
    institution_short_name: str = "Municipalidad"
    contact_email: str = "soporte@municipalidad.gob.pe"

    # ── Seguridad ─────────────────────────────────────────────
    secret_key: str = "desarrollo-clave-insegura-cambiar-en-produccion-32c"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 4
    login_max_attempts: int = 5
    login_lock_minutes: int = 15
    rate_limit_per_minute: int = 300
    license_encryption_key: str = ""

    # ── Datos ─────────────────────────────────────────────────
    mongo_uri: str = "mongodb://mongo:27017/?replicaSet=rs0"
    mongo_db: str = "mesa_ayuda"
    redis_url: str = "redis://redis:6379/0"

    # ── Archivos ──────────────────────────────────────────────
    upload_dir: str = "/data/uploads"
    max_upload_mb: int = 15
    clamav_enabled: bool = True
    clamav_host: str = "clamav"
    clamav_port: int = 3310

    # ── IA ────────────────────────────────────────────────────
    ai_global_enabled: bool = True
    ai_learning_enabled: bool = True
    ai_provider: str = "desactivado"
    ai_base_url: str = "http://llm:11434/v1"
    ai_api_key: str = "local"
    ai_model: str = "qwen2.5:7b"
    ai_timeout_seconds: int = 60
    ai_max_tokens: int = 1200
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"
    chatbot_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    chatbot_limite_consultas_tecnico: int = 15
    ai_recommendations_enabled: bool = True
    ai_recommendations_default: bool = True

    # ── Exportes ──────────────────────────────────────────────
    export_dir: str = "/data/exports"

    # ── Validaciones ──────────────────────────────────────────
    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("business_timezone")
    @classmethod
    def _valid_tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:  # pragma: no cover
            raise ValueError(f"Zona horaria de negocio invalida: {value}") from exc
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.business_timezone)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def public_summary(self) -> dict[str, object]:
        """Resumen sin secretos, para la pantalla de Configuracion y health."""
        return {
            "app_name": self.app_name,
            "app_env": self.app_env,
            "business_timezone": self.business_timezone,
            "institution_name": self.institution_name,
            "ai_global_enabled": self.ai_global_enabled,
            "ai_recommendations_enabled": self.ai_recommendations_enabled,
            "max_upload_mb": self.max_upload_mb,
            "clamav_enabled": self.clamav_enabled,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def reload_settings() -> None:
    """Usado por las pruebas y por el endpoint de recarga (solo admin)."""
    get_settings.cache_clear()
    global settings
    try:
        settings = get_settings()
    except Exception:  # pragma: no cover - deja el valor anterior
        settings = Settings()


__all__ = ["BASE_DIR", "Settings", "get_settings", "settings", "reload_settings", "functools"]
