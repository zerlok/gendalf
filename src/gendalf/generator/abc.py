import abc

from gendalf.generator.model import CodeGeneratorContext, CodeGeneratorResult


class CodeGenerator(metaclass=abc.ABCMeta):
    """Interface for code generators used by `gendalf`."""

    @abc.abstractmethod
    def generate(self, context: CodeGeneratorContext) -> CodeGeneratorResult:
        raise NotImplementedError
