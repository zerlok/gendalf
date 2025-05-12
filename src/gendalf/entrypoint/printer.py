import io
import typing as t
from dataclasses import replace

from astlab.info import ModuleInfo, TypeInfo

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

        self.__writer(f"* {info.name} ({type_.qualname}){' ' if info.doc else ''}{info.doc or ''}")

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
                    type_=self.__to_iterator(info.input_.type_),
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
        returns: t.Optional[TypeInfo],
    ) -> None:
        with io.StringIO() as ss:
            ss.write(f"   * {info.name}(")

            for i, param in enumerate(params):
                if i > 0:
                    ss.write(", ")

                ss.write(f"{param.name}: {param.type_.annotation()}")
                if param.default.is_set:
                    ss.write(f" = {param.default.value()}")

            ss.write(")")
            if returns is not None:
                ss.write(f" -> {returns.annotation()}")

            if info.doc:
                ss.write(f": {info.doc}")

            self.__writer(ss.getvalue())

    def __to_iterator(self, type_: TypeInfo) -> TypeInfo:
        return TypeInfo(name="Iterator", module=ModuleInfo(None, "typing"), type_params=(type_,))
