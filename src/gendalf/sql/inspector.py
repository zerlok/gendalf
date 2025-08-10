import re
import typing as t
import warnings
from dataclasses import replace
from functools import cached_property
from pathlib import Path

from astlab.types import NamedTypeInfo, TypeInfo, predef
from sqlglot import Dialect, Expression, MappingSchema, parse
from sqlglot.expressions import (
    EQ,
    GT,
    GTE,
    LT,
    LTE,
    NEQ,
    Column,
    ColumnDef,
    Create,
    DataType,
    DefaultColumnConstraint,
    ILike,
    Is,
    Like,
    Limit,
    NotNullColumnConstraint,
    Offset,
    Placeholder,
    PrimaryKeyColumnConstraint,
    Schema,
    Table,
)
from sqlglot.optimizer.annotate_types import TypeAnnotator, annotate_types
from sqlglot.optimizer.qualify import qualify

from gendalf.sql.model import (
    ColumnInfo,
    FetchMode,
    ParameterInfo,
    ParametrizedQueryInfo,
    RecordInfo,
    SimpleQueryInfo,
    SQLInfo,
    TableInfo,
)


class SQLInspector:
    def __init__(self, dialect: str) -> None:
        self.__dialect_name = dialect
        self.__dialect = Dialect.get_or_raise(self.__dialect_name)

    def inspect_source(self, source: Path) -> t.Iterable[SQLInfo]:
        return self.inspect_paths(source.rglob("*.sql"))

    def inspect_paths(self, paths: t.Iterable[Path]) -> t.Iterable[SQLInfo]:
        parsed = [(path, self.__parse(path)) for path in paths]

        schema = self.__build_schema(parsed)

        for path, expressions in parsed:
            tables = list[TableInfo]()
            queries = list[ParametrizedQueryInfo]()

            for expr in self.__annotate(expressions, schema):
                table = self.__extract_table(expr)
                if table is not None:
                    tables.append(table)

                query = self.__extract_query(expr)
                if query is not None:
                    queries.append(query)

            yield SQLInfo(
                path=path,
                dialect=self.__dialect_name,
                tables=tables,
                queries=queries,
            )

    def __parse(self, path: Path) -> t.Sequence[Expression]:
        return [self.__normalize(expr) for expr in parse(path.read_text(), dialect=self.__dialect)]

    def __normalize(self, expr: Expression) -> Expression:
        qualified = qualify(expr, dialect=self.__dialect)

        for node in expr.dfs():
            if isinstance(node, ColumnDef):
                if "nullable" not in node.kind.args:
                    nullable = not any(
                        isinstance(c.kind, (PrimaryKeyColumnConstraint, NotNullColumnConstraint))
                        for c in node.constraints
                    )
                    node.kind.set("nullable", nullable)

        return qualified

    def __build_schema(self, parsed: t.Sequence[tuple[Path, t.Sequence[Expression]]]) -> MappingSchema:
        schema = MappingSchema(dialect=self.__dialect)

        for _, expressions in parsed:
            for expr in expressions:
                if (
                    not isinstance(expr, Create)
                    or not isinstance(expr.this, Schema)
                    or not isinstance(expr.this.this, Table)
                ):
                    continue

                schema_expr: Schema = expr.this
                table_expr: Table = expr.this.this

                schema.add_table(
                    table=table_expr,
                    column_mapping={col: col.kind for col in schema_expr.expressions if isinstance(col, ColumnDef)},
                )

        return schema

    def __annotate(self, expressions: t.Sequence[Expression], schema: MappingSchema) -> t.Iterable[Expression]:
        for expr in expressions:
            # TODO: support `insert`, `update`, `delete` and other statements.
            yield annotate_types(expr, schema=schema, annotators={**self.__dialect.ANNOTATORS}, dialect=self.__dialect)

    def __extract_table(self, expr: Expression) -> t.Optional[TableInfo]:
        if not isinstance(expr, Create) or not isinstance(expr.this, Schema) or not isinstance(expr.this.this, Table):
            return None

        schema_expr: Schema = expr.this
        table_expr: Table = expr.this.this

        return TableInfo(
            name=table_expr.name,
            columns=[
                ColumnInfo(
                    name=column.name,
                    type_=self.__extract_column_type(column),
                    has_default=self.__has_column_default(column),
                )
                for column in schema_expr.expressions
                if isinstance(column, ColumnDef)
            ],
            query=SimpleQueryInfo(
                name=self.__extract_query_name(expr.comments),
                statement=expr.sql(dialect=self.__dialect, comments=False, pretty=False),
            ),
        )

    def __extract_query(self, expr: Expression) -> t.Optional[ParametrizedQueryInfo]:
        name, fetch = self.__extract_query_info(expr.comments)

        return ParametrizedQueryInfo(
            name=name,
            # TODO: replace placeholders (e.g. $1, $2, etc.)
            # TODO: consider param type cast in SQL
            statement=expr.sql(dialect=self.__dialect, comments=False, pretty=False),
            params=[
                ParameterInfo(name=node.this, type_=self.__extract_param_type(node))
                for node in expr.find_all(Placeholder)
            ],
            fetch=fetch if fetch is not None else "exec" if isinstance(expr, Create) else "many",
            # TODO: add returning fields (select & returning)
            returns=RecordInfo(fields=()),
        )

    def __extract_param_type(self, node: Placeholder) -> TypeInfo:
        parent = node.parent
        if parent is None:
            msg = "placeholder must be a part of expression"
            raise ValueError(msg, node)

        if isinstance(parent, (Is, EQ, NEQ, GT, GTE, LT, LTE, Like, ILike)):
            return (
                self.__extract_expression_type(parent.this)
                if parent.expression is node
                else self.__extract_expression_type(parent.expression)
            )

        elif isinstance(parent, (Limit, Offset)):
            return predef().int

        # TODO: support more expressions
        else:
            warnings.warn(f"can't infer parameter type for {node!r}, continuing with any", RuntimeWarning)
            return predef().any

    def __extract_expression_type(self, node: Expression) -> TypeInfo:
        if node.type is None:
            warnings.warn(f"can't extract {node!r} expression type, continuing with any", RuntimeWarning)
            return predef().any

        return self.__extract_py_type(node.type)

    def __extract_column_type(self, column: t.Union[Column, ColumnDef]) -> TypeInfo:
        if column.kind is None or column.kind.type is None:
            warnings.warn(f"column {column!r} has no type info, continuing with any", RuntimeWarning)
            return predef().any

        return self.__extract_py_type(column.kind.type)

    def __extract_py_type(self, type_: DataType) -> TypeInfo:
        py_type = self.__sql2py_type_map.get(type_.this)

        if py_type is None:
            warnings.warn(f"data type {type_!r} is not supported, continuing with any", RuntimeWarning)
            return predef().any

        if type_.args.get("nullable"):
            py_type = replace(predef().optional, type_params=(py_type,))

        return py_type

    def __has_column_default(self, column: ColumnDef) -> bool:
        return any(isinstance(c.kind, DefaultColumnConstraint) for c in column.constraints)

    def __extract_query_name(self, comments: t.Sequence[str]) -> str:
        for comment in comments:
            match = self.__query_info_pattern.search(comment)
            if match is not None:
                return match.group("name")

        msg = "query name was not specified"
        raise ValueError(msg, comments)

    def __extract_query_info(self, comments: t.Sequence[str]) -> tuple[str, t.Optional[FetchMode]]:
        for comment in comments:
            match = self.__query_info_pattern.search(comment)
            if match is not None:
                return match.group("name"), match.group("fetch")

        msg = "query name was not specified"
        raise ValueError(msg, comments)

    @cached_property
    def __sql2py_type_map(self) -> t.Mapping[DataType.Type, TypeInfo]:
        return {
            sql_type: py_type
            for sql_types, py_type in [
                ([DataType.Type.BOOLEAN], predef().bool),
                ([DataType.Type.SERIAL, DataType.Type.BIGSERIAL, DataType.Type.SMALLSERIAL], predef().int),
                (DataType.INTEGER_TYPES, predef().int),
                (DataType.FLOAT_TYPES, predef().float),
                (DataType.TEXT_TYPES, predef().str),
                (DataType.REAL_TYPES, NamedTypeInfo.build("decimal", "Decimal")),
                (DataType.TEMPORAL_TYPES, NamedTypeInfo.build("datetime", "datetime")),
                ([DataType.Type.INTERVAL], NamedTypeInfo.build("datetime", "timedelta")),
                (DataType.ARRAY_TYPES, predef().list),
                ([DataType.Type.NESTED], predef().mapping),
                ([DataType.Type.MAP], predef().mapping),
                ([DataType.Type.OBJECT], predef().object),
                ([DataType.Type.STRUCT], predef().mapping),
                ([DataType.Type.UNION], predef().union),
            ]
            for sql_type in sql_types
        }

    @cached_property
    def __query_info_pattern(self) -> t.Pattern[str]:
        return re.compile(r"\s*name:\s*(?P<name>\w+)(?:\s*:(?P<fetch>exec|one|many))?")


class SQLAnnotator(TypeAnnotator):
    pass
