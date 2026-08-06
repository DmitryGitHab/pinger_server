"""Pydantic-схемы запросов и ответов.

Раньше main.py принимал `ip_info: dict` без валидации формы запроса —
опечатка в ключе ("ip" vs "IP") падала бы в рантайме с KeyError вместо
понятной 422-ошибки от FastAPI. Здесь используются типизированные модели,
поэтому FastAPI сам валидирует вход и генерирует корректную OpenAPI-схему.
"""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from config import IP_REGEX


class IPCreate(BaseModel):
    """Тело запроса на добавление/изменение IP."""

    ip: str

    @field_validator("ip")
    @classmethod
    def validate_ip_format(cls, value: str) -> str:
        if not re.match(IP_REGEX, value):
            raise ValueError("Invalid IPv4 address format")
        return value


class IPInfo(BaseModel):
    """Метрики конкретного IP — используется как response_model."""

    ip: str
    ping: Optional[float] = None
    packet_loss: Optional[float] = None
    packet_received: Optional[float] = None
    last_successful_ping: Optional[datetime] = None

    class Config:
        from_attributes = True
