import abc

from gendalf.model import GeneratorContext, GeneratorResult


class CodeGenerator(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def generate(self, context: GeneratorContext) -> GeneratorResult:
        raise NotImplementedError
