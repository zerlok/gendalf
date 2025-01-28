import typing as t
from functools import partial

from gendalf.model import EntrypointOptions

T = t.TypeVar("T")
__ENTRYPOINT_CONFIG = """__gendalf_entrypoint_config__"""


@t.overload
def entrypoint(obj: type[T]) -> type[T]: ...


@t.overload
def entrypoint(*, name: str) -> t.Callable[[type[T]], type[T]]: ...


def entrypoint(
    obj: t.Optional[type[T]] = None,
    name: t.Optional[str] = None,
) -> t.Union[type[T], t.Callable[[type[T]], type[T]]]:
    return (
        _mark_entrypoint(obj, EntrypointOptions())
        if obj is not None
        # NOTE: mypy thinks that `T` of `_mark_entrypoint` is not the same `T` of `entrypoint`
        else t.cast(t.Callable[[type[T]], type[T]], partial(_mark_entrypoint, options=EntrypointOptions(name=name)))
    )


def _mark_entrypoint(obj: type[T], options: EntrypointOptions) -> type[T]:
    setattr(obj, __ENTRYPOINT_CONFIG, options)
    return obj


def get_entrypoint_options(obj: object) -> t.Optional[EntrypointOptions]:
    opts: object = getattr(obj, __ENTRYPOINT_CONFIG, None)
    assert opts is None or isinstance(opts, EntrypointOptions)
    return opts
