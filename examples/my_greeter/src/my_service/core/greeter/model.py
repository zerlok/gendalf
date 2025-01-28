from dataclasses import dataclass
from datetime import datetime

# UserId = t.NewType("UserId", int)


@dataclass(frozen=True)
class SessionInfo:
    start: datetime


@dataclass(frozen=True)
class UserInfo:
    id_: int
    name: str
    # session: SessionInfo
