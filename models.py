from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class IPInfo(BaseModel):
    ip: str
    ping: Optional[float] = None
    packet_loss: Optional[float] = None
    packet_received: Optional[float] = None  # Новое поле
    last_successful_ping: Optional[datetime] = None