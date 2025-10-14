import re
import typing as t
import warnings
from dataclasses import replace
from functools import cached_property
from pathlib import Path
from pprint import pprint

from astlab.types import NamedTypeInfo, TypeInfo, predef
from sqlglot import Dialect, exp, parse

from gendalf.sql.annotator import SQLAnnotator
from gendalf.sql.model import (
    ColumnInfo,
    FetchMode,
    FieldInfo,
    ParameterInfo,
    QueryInfo,
    RecordInfo,
    SQLInfo,
    TableInfo,
)


class SQLInspector:
    def __init__(self, dialect: str) -> None:
        self.__dialect_name = dialect
        self.__dialect = Dialect.get_or_raise(self.__dialect_name)
        self.__annotator = SQLAnnotator(self.__dialect)

    def inspect_source(self, source: Path) -> t.Iterable[SQLInfo]:
        return self.inspect_paths(source.rglob("*.sql"))

    def inspect_paths(self, paths: t.Iterable[Path]) -> t.Iterable[SQLInfo]:
        parsed = [(path, self.__parse(path)) for path in paths]

        annotations = self.__build_annotations(parsed)

        for path, expressions in parsed:
            tables = list[TableInfo]()
            queries = list[QueryInfo]()

            for original in expressions:
                annotated = annotations[original]

                table = self.__extract_table(original, annotated)
                if table is not None:
                    tables.append(table)
                    continue

                query = self.__extract_query(original, annotated)
                if query is not None:
                    queries.append(query)

            yield SQLInfo(
                path=path,
                dialect=self.__dialect_name,
                tables=tables,
                queries=queries,
            )

    def __parse(self, path: Path) -> t.Sequence[exp.Expression]:
        return list(parse(path.read_text(), dialect=self.__dialect))

    def __build_annotations(
        self,
        parsed: t.Sequence[tuple[Path, t.Sequence[exp.Expression]]],
    ) -> t.Mapping[exp.Expression, exp.Expression]:
        originals = [expression for _, expressions in parsed for expression in expressions]
        return dict(zip(originals, self.__annotator.annotate(originals)))

    def __extract_table(self, original: exp.Expression, annotated: exp.Expression) -> t.Optional[TableInfo]:
        if (
            not isinstance(annotated, exp.Create)
            or not isinstance(annotated.this, exp.Schema)
            or not isinstance(annotated.this.this, exp.Table)
        ):
            return None

        schema_expr: exp.Schema = annotated.this
        table_expr: exp.Table = annotated.this.this

        return TableInfo(
            name=table_expr.name,
            columns=[
                ColumnInfo(
                    name=column.name,
                    type_=self.__extract_column_type(column),
                    has_default=self.__has_column_default(column),
                )
                for column in schema_expr.expressions
                if isinstance(column, exp.ColumnDef)
            ],
            query=QueryInfo(
                name=self.__extract_query_name(annotated),
                statement=self.__render_statement(original),
                params=self.__extract_params(annotated),
            ),
        )

    def __extract_query(self, original: exp.Expression, annotated: exp.Expression) -> t.Optional[QueryInfo]:
        name, fetch = self.__extract_query_info(annotated)

        return QueryInfo(
            name=name,
            statement=self.__render_statement(original),
            params=self.__extract_params(annotated),
            fetch=fetch,
            # TODO: add references to defined table columns to reuse table models
            returns=RecordInfo(
                fields=tuple(
                    FieldInfo(type_=self.__extract_column_type(col), alias=col.name)
                    for col in annotated.type.expressions
                )
                if annotated.type is not None and annotated.type.is_type(exp.DataType.Type.STRUCT)
                else (FieldInfo(type_=self.__extract_expr_type(annotated)),)
            )
            if fetch != "exec"
            else None,
        )

    def __extract_params(self, node: exp.Expression) -> list[ParameterInfo]:
        return [
            ParameterInfo(name=node.this, type_=self.__extract_expr_type(node))
            for node in node.find_all(exp.Placeholder)
        ]

    def __extract_expr_type(self, node: exp.Expression) -> TypeInfo:
        if node.type is None:
            warnings.warn(f"can't extract {node!r} expression type, continuing with any", RuntimeWarning)
            return predef().any

        return self.__extract_py_type(node.type)

    def __extract_column_type(self, column: t.Union[exp.Column, exp.ColumnDef]) -> TypeInfo:
        if column.kind is None:
            warnings.warn(f"column {column!r} has no type info, continuing with any", RuntimeWarning)
            return predef().any

        return self.__extract_py_type(column.kind)

    def __extract_py_type(self, dtype: exp.DataType) -> TypeInfo:
        py_type = self.__sql2py_type_map.get(dtype.this)

        if py_type is None:
            warnings.warn(f"data type {dtype!r} is not supported, continuing with any", RuntimeWarning)
            return predef().any

        if dtype.args.get("nullable"):
            py_type = replace(predef().optional, type_params=(py_type,))

        return py_type

    def __has_column_default(self, column: exp.ColumnDef) -> bool:
        return any(isinstance(c.kind, exp.DefaultColumnConstraint) for c in column.constraints)

    def __extract_query_name(self, node: exp.Expression) -> str:
        for comment in node.comments:
            match = self.__query_info_pattern.search(comment)
            if match is not None:
                return match.group("name")

        msg = "query name was not specified"
        raise ValueError(msg, node)

    def __extract_query_info(self, node: exp.Expression) -> tuple[str, FetchMode]:
        for comment in node.comments:
            match = self.__query_info_pattern.search(comment)
            if match is not None:
                name = match.group("name")
                fetch = match.group("fetch") or self.__detect_fetch_mode(node)
                return name, fetch

        msg = "query name was not specified"
        raise ValueError(msg, node.comments)

    def __detect_fetch_mode(self, node: exp.Expression) -> FetchMode:
        if node.type is None:
            return "exec"

        elif node.type.is_type(exp.DataType.Type.STRUCT):
            if len(node.type.expressions) == 0:
                return "exec"

            elif len(node.type.expressions) == 1:
                return "scalar"

            else:
                return "many"

        elif node.type.is_type(*exp.DataType.STRUCT_TYPES):
            return "many"

        else:
            return "scalar"

    def __render_statement(self, node: exp.Expression) -> str:
        # TODO: replace placeholders (e.g. $1, $2, etc.)
        return self.__dialect.generate(node, comments=False, pretty=False)

    @cached_property
    def __sql2py_type_map(self) -> t.Mapping[exp.DataType.Type, TypeInfo]:
        return {
            sql_type: py_type
            for sql_types, py_type in [
                ([exp.DataType.Type.BOOLEAN], predef().bool),
                ([exp.DataType.Type.SERIAL, exp.DataType.Type.BIGSERIAL, exp.DataType.Type.SMALLSERIAL], predef().int),
                (exp.DataType.INTEGER_TYPES, predef().int),
                (exp.DataType.FLOAT_TYPES, predef().float),
                (exp.DataType.TEXT_TYPES, predef().str),
                (exp.DataType.REAL_TYPES, NamedTypeInfo.build("decimal", "Decimal")),
                (exp.DataType.TEMPORAL_TYPES, NamedTypeInfo.build("datetime", "datetime")),
                ([exp.DataType.Type.INTERVAL], NamedTypeInfo.build("datetime", "timedelta")),
                (exp.DataType.ARRAY_TYPES, predef().list),
                ([exp.DataType.Type.NESTED], predef().mapping),
                ([exp.DataType.Type.MAP], predef().mapping),
                ([exp.DataType.Type.OBJECT], predef().object),
                ([exp.DataType.Type.STRUCT], predef().mapping),
                ([exp.DataType.Type.UNION], predef().union),
            ]
            for sql_type in sql_types
        }

    @cached_property
    def __query_info_pattern(self) -> t.Pattern[str]:
        return re.compile(r"\s*name:\s*(?P<name>\w+)(?:\s*:(?P<fetch>exec|one|many))?")


if __name__ == "__main__":
    pprint(list(SQLInspector("postgres").inspect_source(Path("examples/my_greeter/src/my_service/db"))))
