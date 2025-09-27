from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UsersRecord:
    id: int
    name: str
    created_at: datetime
