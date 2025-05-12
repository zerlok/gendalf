import abc

from gendalf.generator.model import CodeGeneratorContext, CodeGeneratorResult


class CodeGenerator(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def generate(self, context: CodeGeneratorContext) -> CodeGeneratorResult:
        raise NotImplementedError
