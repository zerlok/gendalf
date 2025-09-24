from __future__ import annotations

import typing as t
from dataclasses import dataclass, field
from functools import singledispatchmethod

from sqlglot.expressions import DataType


@dataclass(frozen=True, kw_only=True)
class UnitType:
    pass


@dataclass(frozen=True, kw_only=True)
class NullableType:
    of_type: ExpressionType


@dataclass(frozen=True, kw_only=True)
class ScalarType:
    dtype: DataType.Type
    vars: t.Sequence[TypeVar] = field(default_factory=tuple)


@dataclass(frozen=True, kw_only=True)
class TupleType:
    args: t.Sequence[ExpressionType]


@dataclass(frozen=True, kw_only=True)
class RecordType:
    columns: t.Sequence[tuple[str, ExpressionType]]


@dataclass(frozen=True, kw_only=True)
class UnionType:
    args: t.Sequence[ExpressionType]


@dataclass(frozen=True, kw_only=True)
class FuncType:
    params: t.Sequence[ExpressionType]
    returns: ExpressionType


@dataclass(frozen=True, kw_only=True)
class TypeVar:
    name: t.Optional[str] = None
    lower: t.Optional[ExpressionType] = None
    upper: t.Optional[ExpressionType] = None


ExpressionType = t.Union[
    UnitType,
    NullableType,
    ScalarType,
    TupleType,
    RecordType,
    UnionType,
    FuncType,
    TypeVar,
]


class TypeSystem:
    def is_type(self, this: ExpressionType, *others: ExpressionType) -> bool:
        return any(self._check(this, other) for other in others)

    @singledispatchmethod
    def _check(self, this: ExpressionType, other: ExpressionType) -> bool:
        raise NotImplementedError

    @_check.register
    def _check_unit(self, this: UnitType, other: ExpressionType) -> bool:
        return isinstance(this, UnitType)

    @_check.register
    def _check_nullable(self, this: NullableType, other: ExpressionType) -> bool:
        return self._check(this.of_type, other.of_type if isinstance(other, NullableType) else other)

    @_check.register
    def _check_scalar(self, this: ScalarType, other: ExpressionType) -> bool:
        if isinstance(other, ScalarType):
            return other.dtype == this.dtype

        return False

    @_check.register
    def _check_tuple(self, this: TupleType, other: ExpressionType) -> bool:
        if isinstance(other, TupleType) and len(this.args) == len(other.args):
            return all(self._check(this_arg, other_arg) for this_arg, other_arg in zip(this.args, other.args))

        return False

    @_check.register
    def _check_record(self, this: RecordType, other: ExpressionType) -> bool:
        if isinstance(other, RecordType) and len(this.columns) == len(other.columns):
            return all(self._check(this_col, other_col) for this_col, other_col in zip(this.columns, other.columns))

        return False

    @_check.register
    def _check_union(self, this: UnionType, other: ExpressionType) -> bool:
        return any(self._check(arg, other) for arg in this.args)

    @_check.register
    def _check_func(self, this: FuncType, other: ExpressionType) -> bool:
        if isinstance(other, FuncType) and len(this.params) == len(other.params):
            return self._check(this.returns, other.returns) and all(
                self._check(this_param, other_param) for this_param, other_param in zip(this.params, other.params)
            )

        return False

    # @cached_property
    # def __dtype_relation_map(self) -> t.Mapping[DataType.Type, t.Collection[DataType.Type]]:
    #     return {
    #         DataType.Type
    #     }
