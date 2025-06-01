from __future__ import annotations

import typing as t
from dataclasses import dataclass
from functools import partial

T = t.TypeVar("T")


@dataclass(frozen=True)
class EntrypointConfig:
    name: t.Optional[str] = None
    version: t.Optional[str] = None


__ENTRYPOINT_CONFIG_ATTR: t.Final[str] = """__gendalf_entrypoint_config__"""


@t.overload
def entrypoint(obj: type[T]) -> type[T]: ...


@t.overload
def entrypoint(*, name: str) -> t.Callable[[type[T]], type[T]]: ...


def entrypoint(
    obj: t.Optional[type[T]] = None,
    name: t.Optional[str] = None,
) -> t.Union[type[T], t.Callable[[type[T]], type[T]]]:
    return (
        _mark_entrypoint(obj, EntrypointConfig())
        if obj is not None
        # NOTE: mypy thinks that `T` of `_mark_entrypoint` is not the same `T` of `entrypoint`
        else t.cast("t.Callable[[type[T]], type[T]]", partial(_mark_entrypoint, options=EntrypointConfig(name=name)))
    )


def _mark_entrypoint(obj: type[T], options: EntrypointConfig) -> type[T]:
    setattr(obj, __ENTRYPOINT_CONFIG_ATTR, options)
    return obj


def get_entrypoint_options(obj: object) -> t.Optional[EntrypointConfig]:
    opts: object = getattr(obj, __ENTRYPOINT_CONFIG_ATTR, None)
    assert opts is None or isinstance(opts, EntrypointConfig)
    return opts
