import re
import typing as t
from functools import cache


def camel2snake(value: str) -> str:
    return _get_camel2snake_pattern().sub(_replace_underscore_group1_lower, value).lower()


def snake2camel(value: str) -> str:
    return _get_snake2camel_pattern().sub(_replace_group1_title, value)


# NOTE: `cache` uses `typing.Any`
@cache  # type: ignore[misc]
def _get_camel2snake_pattern() -> t.Pattern[str]:
    return re.compile(r"(?!^)_?([A-Z])(?=[a-z])")


def _replace_underscore_group1_lower(match: t.Match[str]) -> str:
    return "_" + match.group(1).lower()  # type: ignore[misc]


# NOTE: `cache` uses `typing.Any`
@cache  # type: ignore[misc]
def _get_snake2camel_pattern() -> t.Pattern[str]:
    return re.compile(r"([^_])([^_]*)(_*)")


def _replace_group1_title(match: t.Match[str]) -> str:
    return match.group(1).upper() + match.group(2)  # type: ignore[misc]
