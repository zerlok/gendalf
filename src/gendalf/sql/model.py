__all__ = [
    "ColumnInfo",
    "FetchMode",
    "ParameterInfo",
    "ParametrizedQueryInfo",
    "RecordInfo",
    "SQLInfo",
    "SimpleQueryInfo",
    "TableInfo",
]

import typing as t
from dataclasses import dataclass
from pathlib import Path

from astlab.types import TypeInfo

FetchMode = t.Literal["exec", "one", "many"]


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
class SimpleQueryInfo:
    name: str
    statement: str


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: t.Sequence[ColumnInfo]
    query: SimpleQueryInfo


@dataclass(frozen=True)
class SimpleFieldInfo:
    type_: TypeInfo
    alias: t.Optional[str] = None


@dataclass(frozen=True)
class TableColumnRefFieldInfo:
    table: TableInfo
    column: ColumnInfo
    alias: t.Optional[str] = None


FieldInfo = t.Union[SimpleFieldInfo, TableColumnRefFieldInfo]


@dataclass(frozen=True)
class RecordInfo:
    fields: t.Sequence[FieldInfo]


@dataclass(frozen=True)
class ParametrizedQueryInfo(SimpleQueryInfo):
    params: t.Sequence[ParameterInfo]
    fetch: FetchMode
    returns: RecordInfo


@dataclass(frozen=True)
class SQLInfo:
    path: Path
    dialect: str
    tables: t.Sequence[TableInfo]
    queries: t.Sequence[ParametrizedQueryInfo]
