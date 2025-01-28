__all__ = [
    "Self",
    "TypeAlias",
    "TypeGuard",
    "assert_never",
    "override",
]

import typing as t

# NOTE: this allows to use methods with `Self` during runtime (when typing_extensions is not installed).
if t.TYPE_CHECKING:
    from typing_extensions import Self, TypeAlias, TypeGuard, assert_never, override

else:
    Self = t.Any
    TypeAlias = t.Any
    TypeGuard = t.Optional

    def assert_never(*args: object, **kwargs: object) -> t.NoReturn:
        raise RuntimeError(args, kwargs)  # pragma: no cover

    def override(func: object) -> object:
        return func
