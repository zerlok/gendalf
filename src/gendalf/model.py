from __future__ import annotations

import abc
import typing as t
from dataclasses import dataclass, field

from gendalf._typing import TypeAlias, override
from gendalf.option import Option

if t.TYPE_CHECKING:
    from astlab.types import NamedTypeInfo, TypeInfo


class Visitable(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def accept(self, visitor: Visitor) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class _BaseMethodInfo:
    name: str
    is_async: bool
    doc: t.Optional[str]


@dataclass(frozen=True)
class ParameterInfo(Visitable):
    name: str
    type_: TypeInfo
    default: Option[object] = field(default_factory=Option[object].empty)

    @override
    def accept(self, visitor: Visitor) -> None:
        visitor.visit_parameter(self)


@dataclass(frozen=True)
class UnaryUnaryMethodInfo(_BaseMethodInfo, Visitable):
    params: t.Sequence[ParameterInfo]
    returns: t.Optional[TypeInfo]

    @override
    def accept(self, visitor: Visitor) -> None:
        visitor.visit_method_unary_unary(self)


@dataclass(frozen=True)
class StreamStreamMethodInfo(_BaseMethodInfo, Visitable):
    input_: ParameterInfo
    output: t.Optional[TypeInfo]

    @override
    def accept(self, visitor: Visitor) -> None:
        visitor.visit_method_stream_stream(self)


MethodInfo: TypeAlias = t.Union[UnaryUnaryMethodInfo, StreamStreamMethodInfo]


@dataclass(frozen=True)
class EntrypointInfo(Visitable):
    name: str
    type_: NamedTypeInfo
    methods: t.Sequence[MethodInfo]
    doc: t.Optional[str]

    @override
    def accept(self, visitor: Visitor) -> None:
        visitor.visit_entrypoint(self)


class Visitor(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def visit_entrypoint(self, info: EntrypointInfo) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def visit_method_unary_unary(self, info: UnaryUnaryMethodInfo) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def visit_method_stream_stream(self, info: StreamStreamMethodInfo) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def visit_parameter(self, info: ParameterInfo) -> None:
        raise NotImplementedError
