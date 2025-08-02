from __future__ import annotations

__all__ = ["Option"]

import typing as t

from typing_extensions import override

T = t.TypeVar("T")
D = t.TypeVar("D")


class _NotSet:
    __slots__ = ()

    @override
    def __str__(self) -> str:
        return "<NotSet>"

    __repr__ = __str__


_NOT_SET: t.Final[_NotSet] = _NotSet()


class Option(t.Generic[T]):
    __slots__ = ("__value",)

    @classmethod
    def empty(cls) -> Option[T]:
        return cls(_NOT_SET)

    def __init__(self, value: t.Union[T, _NotSet]) -> None:
        self.__value = value

    @override
    def __str__(self) -> str:
        return f"<Option[{self.__value}]>"

    @override
    def __repr__(self) -> str:
        return f"Option({self.__value!r})" if not isinstance(self.__value, _NotSet) else "Option()"

    @property
    def is_set(self) -> bool:
        return not self.is_empty

    @property
    def is_empty(self) -> bool:
        return self.__value is _NOT_SET

    @t.overload
    def value(self) -> t.Optional[T]: ...

    @t.overload
    def value(self, default: D) -> t.Union[T, D]: ...

    def value(self, default: t.Optional[D] = None) -> t.Union[T, t.Optional[D]]:
        return self.__value if not isinstance(self.__value, _NotSet) else default
