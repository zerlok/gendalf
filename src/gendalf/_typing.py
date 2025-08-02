__all__ = [
    "ParamSpec",
    "Self",
    "TypeAlias",
    "TypeGuard",
    "assert_never",
    "override",
]

import typing as t

# NOTE: this allows to use methods with `Self` during runtime (when typing_extensions is not installed).
if t.TYPE_CHECKING:
    from typing_extensions import ParamSpec, Self, TypeAlias, TypeGuard, assert_never, override

else:
    Self = t.Any
    TypeAlias = t.Any
    TypeGuard = t.Optional

    class ParamSpec:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        args = t.Any
        kwargs = t.Any

    def assert_never(*args: object, **kwargs: object) -> t.NoReturn:
        raise RuntimeError(args, kwargs)  # pragma: no cover

    def override(func: object) -> object:
        return func
