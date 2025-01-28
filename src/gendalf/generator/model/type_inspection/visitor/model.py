import typing as t
from dataclasses import dataclass, field

from gendalf._typing import TypeAlias
from gendalf.option import Option


@dataclass(frozen=True)
class _BaseContext:
    type_: type[object]


@dataclass(frozen=True)
class ScalarContext(_BaseContext):
    pass


@dataclass(frozen=True)
class EnumValueContext(_BaseContext):
    name: str
    value: object
    description: t.Optional[str] = None


@dataclass(frozen=True)
class EnumContext(_BaseContext):
    name: t.Optional[str]
    values: t.Sequence[EnumValueContext]
    description: t.Optional[str] = None


@dataclass(frozen=True)
class ContainerContext(_BaseContext):
    origin: type[object]
    inners: t.Sequence[type[object]]


@dataclass(frozen=True)
class StructureFieldContext(_BaseContext):
    name: str
    annotation: type[object]
    default_value: Option[object] = field(default_factory=Option[object].empty)
    description: t.Optional[str] = None


@dataclass(frozen=True)
class StructureContext(_BaseContext):
    name: str
    fields: t.Sequence[StructureFieldContext]
    description: t.Optional[str] = None


Context: TypeAlias = t.Union[
    ScalarContext,
    EnumContext,
    EnumValueContext,
    ContainerContext,
    StructureContext,
    StructureFieldContext,
]
