from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class LogItem(BaseModel):
    type: Literal["url_visit", "copy_event"]
    url: str
    timestamp: datetime
    text: str | None = None
    title: str | None = None
