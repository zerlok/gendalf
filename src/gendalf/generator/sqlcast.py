import typing as t
from contextlib import contextmanager
from functools import cached_property
from itertools import chain

from astlab import package
from astlab.abc import Expr, TypeRef
from astlab.builder import (
    ClassScopeASTBuilder,
    Comprehension,
    FuncArgInfo,
    MethodScopeASTBuilder,
    PackageASTBuilder,
    ScopeASTBuilder,
)
from astlab.types import NamedTypeInfo

from gendalf._typing import override
from gendalf.generator.abc import SQLCodeGenerator
from gendalf.generator.model import CodeGeneratorResult, SQLCodeGeneratorContext
from gendalf.sql.model import FieldInfo, ParameterInfo, QueryInfo, RecordInfo
from gendalf.string_case import snake2camel


# FIXME: inappropriate placeholder / query parameters order
# TODO: support clickhouse driver, sqlalchemy, ...
# TODO: create appropriate models: reuse models for rows from the same tables, but distinct models from different tables
# TODO: support joins: tuple[LeftRow, RightRow]
# TODO: support transactions
# TODO: support many insert
# TODO: flatten simple queries (one column => scalar value)
class SQLCastCodeGenerator(SQLCodeGenerator):
    @override
    def generate(self, context: SQLCodeGeneratorContext) -> CodeGeneratorResult:
        with self.__init_root(context) as pkg:
            registry = self.__build_models(context, pkg)
            self.__build_querier(context, pkg, registry)

        return CodeGeneratorResult(
            files=[
                CodeGeneratorResult.File(
                    path=context.output.joinpath(module.file),
                    content=content,
                )
                for module, content in pkg.render()
            ],
        )

    def __build_models(
        self,
        context: SQLCodeGeneratorContext,
        pkg: PackageASTBuilder,
    ) -> t.Mapping[RecordInfo, TypeRef]:
        registry = dict[RecordInfo, TypeRef]()

        with pkg.module("model") as mod:
            for sql in context.sqls:
                for table in sql.tables:
                    with mod.class_def(f"{snake2camel(table.name)}Row").dataclass(frozen=True) as row_def:
                        for col in table.columns:
                            row_def.field_def(col.name, col.type_)

                    registry[
                        RecordInfo(fields=tuple(FieldInfo(type_=col.type_, alias=col.name) for col in table.columns))
                    ] = row_def.ref()

                for query in sql.queries:
                    if query.returns is not None and query.returns not in registry:
                        # if query.returns is not None:
                        with mod.class_def(f"{snake2camel(query.name)}Row").dataclass(frozen=True) as row_def:
                            for field in query.returns.fields:
                                row_def.field_def(field.alias, field.type_)

                        registry[query.returns] = row_def.ref()

        return registry

    def __build_querier(
        self,
        context: SQLCodeGeneratorContext,
        pkg: PackageASTBuilder,
        registry: t.Mapping[RecordInfo, TypeRef],
    ) -> None:
        with pkg.module("querier") as mod:
            with mod.class_def("AsyncQuerier") as querier:
                with querier.init_self_attrs_def({"pool": self.__asyncpg_pool}):
                    pass

                for sql in context.sqls:
                    for query in chain((table.query for table in sql.tables), sql.queries):
                        if query.fetch == "exec":
                            self.__build_method_exec(querier, query)

                        elif query.fetch == "scalar":
                            self.__build_method_scalar(querier, query)

                        elif query.fetch == "one":
                            self.__build_method_one(querier, query, registry)

                        elif query.fetch == "many":
                            self.__build_method_many(querier, query, registry)

                        else:
                            t.assert_never(query.fetch)

    def __build_method_exec(self, querier: ClassScopeASTBuilder, info: QueryInfo) -> None:
        with (
            self.__query_method_def(querier, info.name, info.params, querier.none()) as method,
            self.__connect(method, info.statement, info.params) as (conn, args),
        ):
            conn.stmt(conn.attr("conn", "execute").call(args=args).await_())

    def __build_method_scalar(self, querier: ClassScopeASTBuilder, info: QueryInfo) -> None:
        returns = info.returns.fields[0] if info.returns is not None and info.returns.fields else None

        with self.__query_method_def(querier, info.name, info.params, returns) as method:
            with self.__connect(method, info.statement, info.params) as (conn, args):
                conn.assign_stmt(
                    target="value",
                    value=conn.attr("conn", "fetchval").call(args=args).await_(),
                )

            method.return_stmt(method.attr("value"))

    def __build_method_one(
        self,
        querier: ClassScopeASTBuilder,
        info: QueryInfo,
        registry: t.Mapping[RecordInfo, TypeRef],
    ) -> None:
        row_type = registry.get(info.returns)
        returns = querier.optional_type(row_type) if row_type is not None else None

        with self.__query_method_def(querier, info.name, info.params, returns) as method:
            with self.__connect(method, info.statement, info.params) as (conn, args):
                conn.assign_stmt(
                    target="row",
                    value=conn.attr("conn", "fetchrow").call(args=args).await_(),
                )

            method.return_stmt(
                method.ternary_not_none_expr(self.__build_row_decoder(method, info, row_type), method.attr("row"))
            )

    def __build_method_many(
        self,
        querier: ClassScopeASTBuilder,
        info: QueryInfo,
        registry: t.Mapping[RecordInfo, TypeRef],
    ) -> None:
        row_type = registry.get(info.returns)
        returns = querier.sequence_type(row_type) if row_type is not None else None

        with self.__query_method_def(querier, info.name, info.params, returns) as method:
            with self.__connect(method, info.statement, info.params) as (conn, args):
                conn.assign_stmt(
                    target="rows",
                    value=conn.attr("conn", "fetch").call(args=args).await_(),
                )

            method.return_stmt(
                method.list_expr(
                    items=Comprehension(
                        target=method.attr("row"),
                        items=method.attr("rows"),
                    ),
                    element=self.__build_row_decoder(method, info, row_type),
                )
            )

    @contextmanager
    def __init_root(self, context: SQLCodeGeneratorContext) -> t.Iterator[PackageASTBuilder]:
        with package(context.package if context.package is not None else "db") as pkg:
            with pkg.init():
                pass

            yield pkg

    @contextmanager
    def __query_method_def(
        self,
        scope: ClassScopeASTBuilder,
        name: str,
        params: t.Sequence[ParameterInfo],
        returns: TypeRef,
    ) -> t.Iterator[MethodScopeASTBuilder]:
        with (
            scope.method_def(name)
            .args([FuncArgInfo(name=param.name, kind="keyword-only", annotation=param.type_) for param in params])
            .returns(returns)
            .async_() as method
        ):
            yield method

    @contextmanager
    def __connect(
        self,
        scope: MethodScopeASTBuilder,
        statement: str,
        params: t.Sequence[ParameterInfo],
    ) -> t.Iterator[tuple[ScopeASTBuilder, t.Sequence[Expr]]]:
        with (
            scope.with_stmt().async_().enter(cm=scope.self_attr("pool", "acquire").call(), name="conn").body() as inner
        ):
            yield (
                inner,
                [
                    scope.const(statement),
                    *(scope.attr(param.name) for param in params),
                ],
            )

    def __build_row_decoder(self, scope: ScopeASTBuilder, info: QueryInfo, row_type: TypeRef) -> Expr:
        return scope.call(
            row_type,
            kwargs={
                field.alias: scope.attr("row").index(scope.const(i)) for i, field in enumerate(info.returns.fields)
            },
        )

    @cached_property
    def __asyncpg_pool(self) -> NamedTypeInfo:
        return NamedTypeInfo.build("asyncpg", "Pool")
