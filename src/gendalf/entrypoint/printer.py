import io
import typing as t
from dataclasses import replace

from astlab.types import TypeAnnotator, TypeInfo, predef

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
    def __init__(self, dest: t.IO[str], annotator: TypeAnnotator) -> None:
        self.__dest = dest
        self.__annotator = annotator

    @override
    def visit_entrypoint(self, info: EntrypointInfo) -> None:
        type_ = info.type_
        assert type_.module is not None

        self.__write_line(f"* {info.name} ({type_.qualname})")
        self.__write_doc(info.doc, 0)

        for method in info.methods:
            method.accept(self)

        self.__write_new_line()

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

    def __write_line(self, line: str, indent: int = 0) -> None:
        self.__write_indent(indent)
        self.__dest.write(line)
        self.__write_new_line()

    def __write_indent(self, indent: int) -> None:
        self.__dest.write(" " * 4 * indent)

    def __write_new_line(self) -> None:
        self.__dest.write("\n")

    def __write_method(
        self,
        info: MethodInfo,
        params: t.Sequence[ParameterInfo],
        returns: t.Optional[TypeInfo],
    ) -> None:
        with io.StringIO() as ss:
            ss.write(f"* {info.name}(")

            for i, param in enumerate(params):
                if i > 0:
                    ss.write(", ")

                ss.write(f"{param.name}: {self.__annotator.annotate(param.type_)}")
                if param.default.is_set:
                    ss.write(f" = {param.default.value()}")

            ss.write(")")
            if returns is not None:
                ss.write(f" -> {self.__annotator.annotate(returns)}")

            self.__write_line(ss.getvalue(), 1)

        self.__write_doc(info.doc, 1)

    def __write_doc(self, doc: t.Optional[str], indent: int) -> None:
        if not doc:
            return

        offset = " " * 4 * (indent + 1)
        normalized_doc = doc.replace("\n", f"\n{offset}")

        self.__write_line(f'"""{normalized_doc}"""', indent + 1)

    def __to_iterator(self, type_: TypeInfo) -> TypeInfo:
        return replace(predef().iterator, type_params=(type_,))
