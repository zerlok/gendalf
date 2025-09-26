import typing as t
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SessionInfo:
    start: datetime


@dataclass(frozen=True)
class UserInfo:
    id_: int
    name: str


@dataclass(frozen=True)
class SystemInfo:
    name: str
    index: int


@dataclass(frozen=True)
class ComplexStructure:
    @dataclass(frozen=True)
    class Item:
        users: t.Sequence[UserInfo]

    items: t.Mapping[str, Item]
