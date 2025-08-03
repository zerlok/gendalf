import abc

from gendalf.generator.model import CodeGeneratorResult, EntrypointCodeGeneratorContext, SQLCodeGeneratorContext


class EntrypointCodeGenerator(metaclass=abc.ABCMeta):
    """Interface for entrypoint code generators used by `gendalf`."""

    @abc.abstractmethod
    def generate(self, context: EntrypointCodeGeneratorContext) -> CodeGeneratorResult:
        raise NotImplementedError


class SQLCodeGenerator(metaclass=abc.ABCMeta):
    """Interface for SQL code generators used by `gendalf`."""

    @abc.abstractmethod
    def generate(self, context: SQLCodeGeneratorContext) -> CodeGeneratorResult:
        raise NotImplementedError
