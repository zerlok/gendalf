__all__ = [
    "ColumnInfo",
    "FetchMode",
    "ParameterInfo",
    "QueryInfo",
    "RowInfo",
    "SQLInfo",
    "TableInfo",
]

import typing as t
from dataclasses import dataclass, field
from pathlib import Path

from astlab.types import TypeInfo

from gendalf.option import Option

FetchMode = t.Literal["exec", "one", "many"]


@dataclass(frozen=True)
class ParameterInfo:
    name: str
    type_: TypeInfo
    default: Option[object] = field(default_factory=Option[object].empty)


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type_: TypeInfo
    default: Option[object] = field(default_factory=Option[object].empty)


@dataclass(frozen=True)
class TableInfo:
    statement: str
    name: str
    columns: t.Sequence[ColumnInfo]


@dataclass(frozen=True)
class RowInfo:
    columns: t.Sequence[ColumnInfo]


@dataclass(frozen=True)
class QueryInfo:
    name: str
    statement: str
    params: t.Sequence[ParameterInfo]
    fetch: FetchMode
    returns: RowInfo


@dataclass(frozen=True)
class SQLInfo:
    path: Path
    dialect: str
    tables: t.Sequence[TableInfo]
    queries: t.Sequence[QueryInfo]
