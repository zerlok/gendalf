from __future__ import annotations

import typing as t
from dataclasses import dataclass
from functools import partial

T = t.TypeVar("T")


@dataclass(frozen=True)
class EntrypointConfig:
    name: t.Optional[str] = None
    enabled: bool = True
    version: t.Optional[str] = None


__ENTRYPOINT_CONFIG_ATTR: t.Final[str] = """__gendalf_entrypoint_config__"""


@t.overload
def entrypoint(type_: type[T]) -> type[T]: ...


@t.overload
def entrypoint(
    *,
    name: t.Optional[str] = None,
    enabled: bool = True,
    version: t.Optional[str] = None,
) -> t.Callable[[type[T]], type[T]]: ...


def entrypoint(
    type_: t.Optional[type[T]] = None,
    *,
    name: t.Optional[str] = None,
    enabled: bool = True,
    version: t.Optional[str] = None,
) -> t.Union[type[T], t.Callable[[type[T]], type[T]]]:
    """
    Mark provided type as an entrypoint to domain layer.

    Such markers are used by `gendalf` CLI.
    """

    config = EntrypointConfig(
        name=name,
        enabled=enabled,
        version=version,
    )

    if type_ is not None:
        return _mark_entrypoint(type_, config)

    # NOTE: mypy thinks that `T` of `_mark_entrypoint` is not the same `T` of `entrypoint`
    return t.cast("t.Callable[[type[T]], type[T]]", partial(_mark_entrypoint, config=config))


def _mark_entrypoint(type_: type[T], config: EntrypointConfig) -> type[T]:
    setattr(type_, __ENTRYPOINT_CONFIG_ATTR, config)
    return type_


def get_entrypoint_config(obj: object) -> t.Optional[EntrypointConfig]:
    opts: object = getattr(obj, __ENTRYPOINT_CONFIG_ATTR, None)
    assert opts is None or isinstance(opts, EntrypointConfig)
    return opts
