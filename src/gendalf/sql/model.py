from __future__ import annotations

__all__ = [
    "ColumnInfo",
    "FetchMode",
    "FieldInfo",
    "ParameterInfo",
    "QueryInfo",
    "RecordInfo",
    "SQLInfo",
    "TableInfo",
]

import typing as t
from dataclasses import dataclass, field
from pathlib import Path

from astlab.types import TypeInfo

FetchMode = t.Literal["exec", "scalar", "one", "many"]


@dataclass(frozen=True)
class ParameterInfo:
    name: str
    type_: TypeInfo


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type_: TypeInfo
    has_default: bool


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: t.Sequence[ColumnInfo]
    query: QueryInfo


@dataclass(frozen=True)
class FieldInfo:
    type_: TypeInfo
    alias: t.Optional[str] = None


@dataclass(frozen=True)
class RecordInfo:
    fields: t.Sequence[FieldInfo]


@dataclass(frozen=True)
class QueryInfo:
    name: str
    statement: str
    fetch: FetchMode = "exec"
    params: t.Sequence[ParameterInfo] = field(default_factory=tuple)
    returns: t.Optional[RecordInfo] = None


@dataclass(frozen=True)
class SQLInfo:
    path: Path
    dialect: str
    tables: t.Sequence[TableInfo]
    queries: t.Sequence[QueryInfo]
