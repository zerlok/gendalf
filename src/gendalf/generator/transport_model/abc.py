import abc

from astlab.builder import ClassHeaderASTBuilder, ModuleASTBuilder


class TMFactory(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def create_class_def(self, builder: ModuleASTBuilder, name: str) -> ClassHeaderASTBuilder:
        raise NotImplementedError
