import os
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Режим разработки
DEVELOPMENT_MODE = True

### Path config ###
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR.parents[1]
API_DIR = SRC_DIR / "api"
DAL_DIR = SRC_DIR / "dal"
DATA_DIR = SRC_DIR.parent / "data"
DATA_DIR = SRC_DIR.parent / "logging"





### Uvicorn Config ###
class UvicornConfig(BaseSettings):
    """
    Конфигурация сервера Uvicorn для FastAPI-приложения.

    Реализует централизованное управление параметрами запуска,
    включая адаптивное количество воркеров, таймауты и безопасность.

    Атрибуты:
        host (str): IP-адрес для привязки сервера.
        port (int): Порт сервера (по умолчанию 8000).
        workers (int): Количество процессов обработки запросов.
        reload (bool): Включить авто-перезагрузку (для development).
        log_level (str): Уровень логирования (debug, info, warning, error, critical).
        access_log (bool): Включить access log (в production лучше выключить).
        timeout_keep_alive (int): Таймаут в секундах для keep-alive соединений.
        loop (str): Цикл событий (uvloop — для production).
        http (str): HTTP-протокол (h11 или auto).
        ws (str): WebSockets-движок (websockets или auto).
        lifespan (str): Управление lifespan (auto, on, off).

    Примеры использования:
        config = UvicornConfig()
        uvicorn.run("app.main:app", **config.model_dump())
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", description="IP-адрес для привязки сервера.")
    port: int = Field(
        default=8000, ge=1, le=65535, description="Порт сервера (1–65535)."
    )
    workers: int = Field(
        default_factory=lambda: (os.cpu_count() or 1) * 2 + 1,
        ge=1,
        description="Количество воркеров (по умолчанию: CPU * 2 + 1).",
    )
    reload: bool = Field(
        default=False,
        description="Включить авто-перезагрузку при изменении кода (development only).",
    )
    log_level: str = Field(
        default="info",
        pattern="^(debug|info|warning|error|critical)$",
        description="Уровень логирования.",
    )
    access_log: bool = Field(default=True, description="Включить access log.")
    timeout_keep_alive: int = Field(
        default=30,
        ge=1,
        le=120,
        description="Таймаут для keep-alive соединений (1–120 сек).",
    )
    loop: str = Field(
        default="uvloop",
        pattern="^(asyncio|uvloop)$",
        description="Цикл событий (uvloop — для максимальной производительности).",
    )
    http: str = Field(
        default="auto", pattern="^(auto|h11|h2)$", description="HTTP-протокол."
    )
    ws: str = Field(
        default="auto", pattern="^(auto|websockets)$", description="WebSocket-движок."
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"debug", "info", "warning", "error", "critical"}
        if v.lower() not in allowed:
            raise ValueError(f"log_level должен быть одним из: {allowed}")
        return v.lower()
    
# 🌟 Глобальный экземпляр конфигурации
uvicorn_config = UvicornConfig()
