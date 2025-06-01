import inspect
import typing as t
from dataclasses import replace

from gendalf._typing import override
from gendalf.model import (
    EntrypointInfo,
    MethodInfo,
    ParameterInfo,
    StreamStreamMethodInfo,
    UnaryUnaryMethodInfo,
    Visitor,
)


class Printer(Visitor):
    def __init__(self, writer: t.Callable[[str], None]) -> None:
        self.__writer = writer

    @override
    def visit_entrypoint(self, info: EntrypointInfo) -> None:
        type_ = info.type_
        assert type_.module is not None

        self.__writer(
            f"* {info.name} ({type_.module.qualname}:{'.'.join(type_.ns)}){' ' if info.doc else ''}{info.doc or ''}"
        )

        for method in info.methods:
            method.accept(self)

        self.__writer("")

    @override
    def visit_method_unary_unary(self, info: UnaryUnaryMethodInfo) -> None:
        self.__write_method(info, info.params, info.returns)

    @override
    def visit_method_stream_stream(self, info: StreamStreamMethodInfo) -> None:
        self.__write_method(
            info=info,
            params=[
                replace(
                    info.input_,
                    annotation=self.__to_iterator(info.input_.annotation),
                ),
            ],
            returns=self.__to_iterator(info.output) if info.output is not None else None,
        )

    @override
    def visit_parameter(self, info: ParameterInfo) -> None:
        pass

    def __write_method(
        self,
        info: MethodInfo,
        params: t.Sequence[ParameterInfo],
        returns: t.Optional[type[object]],
    ) -> None:
        signature = inspect.Signature(
            parameters=[
                inspect.Parameter(
                    name=param.name,
                    # TODO: remove type ignores
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,  # type: ignore[misc]
                    default=param.default.value(inspect.Parameter.empty),  # type: ignore[misc]
                    annotation=param.annotation,
                )
                for param in params
            ],
            return_annotation=returns,
        )
        self.__writer(f"   * {info.name}{signature}: {info.doc or ''}")

    def __to_iterator(self, type_: type[object]) -> type[object]:
        return t.Iterator[type_]  # type: ignore[valid-type]
