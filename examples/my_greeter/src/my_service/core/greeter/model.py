from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SessionInfo:
    start: datetime


@dataclass(frozen=True)
class UserInfo:
    id_: int
    name: str
