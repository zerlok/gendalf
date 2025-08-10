import typing as t
from contextlib import contextmanager
from functools import cached_property

from astlab import package
from astlab.builder import FuncArgInfo, PackageASTBuilder
from astlab.types import NamedTypeInfo

from gendalf._typing import override
from gendalf.generator.abc import SQLCodeGenerator
from gendalf.generator.model import CodeGeneratorResult, SQLCodeGeneratorContext


class SQLCastCodeGenerator(SQLCodeGenerator):
    @override
    def generate(self, context: SQLCodeGeneratorContext) -> CodeGeneratorResult:
        with self.__init_root(context) as pkg:
            with pkg.module("model") as mod:
                # TODO: build model defs, use for returns
                pass

            with pkg.module("querier") as querier:
                with querier.class_def(name="AsyncQuerier") as class_def:
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
