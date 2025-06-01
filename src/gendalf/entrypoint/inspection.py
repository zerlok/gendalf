import abc
import importlib
import inspect
import sys
import typing as t
from pathlib import Path
from types import ModuleType

from astlab.info import TypeInfo
from astlab.reader import import_module, walk_package_modules

from gendalf.entrypoint.decorator import get_entrypoint_options
from gendalf.model import EntrypointInfo, MethodInfo, ParameterInfo, StreamStreamMethodInfo, UnaryUnaryMethodInfo
from gendalf.option import Option


def inspect_source_dir(
    src: Path,
    *,
    ignore_module_on_import_error: bool = False,
) -> t.Iterable[EntrypointInfo]:
    sys.path.append(str(src))
    try:
        for path in walk_package_modules(src):
            if path.stem.startswith("_"):
                continue

            try:
                module = import_module(path)

            except ImportError:
                if not ignore_module_on_import_error:
                    raise

            else:
                yield from inspect_module(module)

    finally:
        importlib.invalidate_caches()
        sys.path.remove(str(src))


def inspect_module(module: ModuleType) -> t.Iterable[EntrypointInfo]:
    for name, obj in inspect.getmembers(module):
        if not inspect.isclass(obj) or obj.__module__ != module.__name__:
            continue

        opts = get_entrypoint_options(obj)
        if opts is None:
            continue

        type_info = TypeInfo.from_type(obj)

        yield EntrypointInfo(
            name=opts.name if opts.name is not None else name,
            type_=type_info,
            methods=tuple(
                inspect_method(member_name, member)
                for member_name, member in inspect.getmembers(obj)
                if not member_name.startswith("_") and callable(member)
            ),
            doc=inspect.getdoc(obj),
        )


class Func(t.Protocol):
    @abc.abstractmethod
    def __call__(self, *args: object, **kwargs: object) -> object:
        raise NotImplementedError


def inspect_method(name: str, func: Func) -> MethodInfo:
    signature = inspect.signature(func)

    params = list(signature.parameters.values())[1:]

    # TODO: uncomment
    if len(params) == 1 and (streaming_type := extract_streaming_type(params[0].annotation)) is not None:
        return StreamStreamMethodInfo(
            name=name,
            input_=_build_param(params[0].replace(annotation=streaming_type)),
            output=extract_streaming_type(signature.return_annotation),
            doc=inspect.getdoc(func),
        )

    return UnaryUnaryMethodInfo(
        name=name,
        # skip `self`
        params=[_build_param(param) for param in params],
        returns=signature.return_annotation,
        doc=inspect.getdoc(func),
    )


def extract_streaming_type(obj: object) -> t.Optional[type[object]]:
    origin = t.get_origin(obj)
    if not isinstance(origin, type) or not issubclass(origin, (t.Iterator, t.AsyncIterator)):
        return None

    args = t.get_args(obj)
    assert len(args) == 1

    # TODO: remove cast, check types
    return t.cast("type[object]", args[0])


def _build_param(param: inspect.Parameter) -> ParameterInfo:
    return ParameterInfo(
        name=param.name,
        annotation=param.annotation,
        default=Option(param.default) if param.default is not param.empty else Option[object].empty(),
    )
