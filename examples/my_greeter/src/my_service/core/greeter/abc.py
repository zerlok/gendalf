import abc
import typing as t


class MessageGenerator(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def gen_message(self, context: t.Mapping[str, object]) -> str:
        raise NotImplementedError
