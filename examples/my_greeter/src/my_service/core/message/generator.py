import typing as t

from my_service.core.greeter.abc import MessageGenerator


class FstringMessageGenerator(MessageGenerator):
    def __init__(self, template_text: str) -> None:
        self.__template_text = template_text

    def gen_message(self, context: t.Mapping[str, object]) -> str:
        return self.__template_text.format(**context)
