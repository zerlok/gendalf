from gendalf._typing import override
from gendalf.generator.abc import SQLCodeGenerator
from gendalf.generator.model import CodeGeneratorResult, SQLCodeGeneratorContext


class SQLCastCodeGenerator(SQLCodeGenerator):
    @override
    def generate(self, context: SQLCodeGeneratorContext) -> CodeGeneratorResult:
        raise NotImplementedError
