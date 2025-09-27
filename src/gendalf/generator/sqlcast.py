import typing as t
from contextlib import contextmanager
from functools import cached_property

from astlab import package
from astlab.builder import FuncArgInfo, PackageASTBuilder
from astlab.types import NamedTypeInfo

from gendalf._typing import override
from gendalf.generator.abc import SQLCodeGenerator
from gendalf.generator.model import CodeGeneratorResult, SQLCodeGeneratorContext
from gendalf.string_case import snake2camel


class SQLCastCodeGenerator(SQLCodeGenerator):
    @override
    def generate(self, context: SQLCodeGeneratorContext) -> CodeGeneratorResult:
        with self.__init_root(context) as pkg:
            with pkg.module("model") as mod:
                for sql in context.sqls:
                    for table in sql.tables:
                        with mod.class_def(f"{table.name}Record").dataclas() as record_def:
                            for col in table.columns:
                                record_def.field_def(col.name, col.type_)

                    for query in sql.queries:
                        if query.fetch == "exec":
                            pass

                        elif query.fetch == "one" or query.fetch == "many":
                            with mod.class_def(f"{snake2camel(query.name)}Result").dataclass() as result_def:
                                for field in query.returns.fields:
                                    result_def.field_def(field.alias, field.type_)

                        else:
                            t.assert_never(query.fetch)

            with pkg.module("querier") as querier:
                with querier.class_def("AsyncQuerier") as class_def:
                    with class_def.init_self_attrs_def({"pool": self.__asyncpg_pool}):
                        pass

                    for sql in context.sqls:
                        for query in sql.queries:
                            # TODO: add `returns` model
                            with (
                                class_def.method_def(query.name)
                                .args(
                                    FuncArgInfo(name=param.name, kind="keyword-only", annotation=param.type_)
                                    for param in query.params
                                )
                                .returns(class_def.ellipsis())
                                .async_() as scope
                            ):
                                with (
                                    scope.with_stmt()
                                    .async_()
                                    .enter(cm=scope.self_attr("pool", "acquire").call(), name="conn")
                                    .body()
                                ):
                                    args = [
                                        scope.const(query.statement),
                                        *(scope.attr(param.name) for param in query.params),
                                    ]

                                    if query.fetch == "exec":
                                        scope.stmt(scope.attr("conn", "execute").call(args=args).await_())

                                    elif query.fetch == "one":
                                        scope.assign_stmt(
                                            target="row",
                                            value=scope.attr("conn", "fetchrow").call(args=args).await_(),
                                        )

                                    elif query.fetch == "many":
                                        scope.assign_stmt(
                                            target="rows",
                                            value=scope.attr("conn", "fetch").call(args=args).await_(),
                                        )

                                    else:
                                        t.assert_never(query.fetch)

        return CodeGeneratorResult(
            files=[
                CodeGeneratorResult.File(
                    path=context.output.joinpath(module.file),
                    content=content,
                )
                for module, content in pkg.render()
            ],
        )

    @contextmanager
    def __init_root(self, context: SQLCodeGeneratorContext) -> t.Iterator[PackageASTBuilder]:
        with package(context.package if context.package is not None else "db") as pkg:
            with pkg.init():
                pass

            yield pkg

    @cached_property
    def __asyncpg_pool(self) -> NamedTypeInfo:
        return NamedTypeInfo.build("asyncpg", "Pool")
