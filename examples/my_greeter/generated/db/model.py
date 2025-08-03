from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class UsersRow:
    id: int
    name: str
    created_at: datetime
