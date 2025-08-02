import abc
import inspect
import typing as t
from pathlib import Path
from types import ModuleType

from astlab.reader import walk_package_modules
from astlab.types import ModuleLoader, NamedTypeInfo, TypeInfo, TypeInspector

from gendalf.entrypoint.decorator import get_entrypoint_config
from gendalf.model import EntrypointInfo, MethodInfo, ParameterInfo, StreamStreamMethodInfo, UnaryUnaryMethodInfo
from gendalf.option import Option


class Func(t.Protocol):
    @abc.abstractmethod
    def __call__(self, *args: object, **kwargs: object) -> object:
        raise NotImplementedError


class EntrypointInspector:
    def __init__(self, loader: ModuleLoader, inspector: TypeInspector) -> None:
        self.__loader = loader
        self.__inspector = inspector

    def inspect_source(
        self,
        source: Path,
        *,
        ignore_module_on_import_error: bool = False,
    ) -> t.Iterable[EntrypointInfo]:
        return self.inspect_paths(
            paths=(path for path in walk_package_modules(source) if not path.stem.startswith("_")),
            ignore_module_on_import_error=ignore_module_on_import_error,
        )

    def inspect_paths(
        self,
        paths: t.Iterable[Path],
        *,
        ignore_module_on_import_error: bool = False,
    ) -> t.Iterable[EntrypointInfo]:
        for path in paths:
            try:
                module = self.__loader.load(path)

            # NOTE: on import error - just ignore the specific path
            except ImportError:  # noqa: PERF203
                if not ignore_module_on_import_error:
                    raise

            else:
                yield from self.inspect_module(module)

    def inspect_module(self, module: ModuleType) -> t.Iterable[EntrypointInfo]:
        for name, obj in inspect.getmembers(module):
            if not inspect.isclass(obj) or obj.__module__ != module.__name__:
                continue

            opts = get_entrypoint_config(obj)
            if opts is None:
                continue

            type_info = self.__inspector.inspect(obj)
            if not isinstance(type_info, NamedTypeInfo):
                msg = "invalid entrypoint type info"
                raise TypeError(msg, type_info)

            yield EntrypointInfo(
                name=opts.name if opts.name is not None else name,
                type_=type_info,
                methods=tuple(
                    self.__inspect_method(member_name, member)
                    for member_name, member in inspect.getmembers(obj)
                    if not member_name.startswith("_") and callable(member)
                ),
                doc=inspect.getdoc(obj),
            )

    def __inspect_method(self, name: str, func: Func) -> MethodInfo:
        signature = inspect.signature(func)

        # skip `self`
        params = list(signature.parameters.values())[1:]

        if len(params) == 1 and (streaming_type := self.__extract_streaming_type(params[0].annotation)) is not None:
            input_stream_param = params[0]
            return StreamStreamMethodInfo(
                name=name,
                is_async=inspect.isasyncgenfunction(func),
                input_=ParameterInfo(
                    name=input_stream_param.name,
                    type_=streaming_type,
                    default=Option(input_stream_param.default)
                    if input_stream_param.default is not input_stream_param.empty
                    else Option[object].empty(),
                ),
                output=self.__extract_streaming_type(signature.return_annotation)
                if signature.return_annotation is not None
                else None,
                doc=inspect.getdoc(func),
            )

        return UnaryUnaryMethodInfo(
            name=name,
            is_async=inspect.iscoroutinefunction(func),
            params=[self.__build_param(param) for param in params],
            returns=self.__inspector.inspect(signature.return_annotation)
            if signature.return_annotation is not None
            else None,
            doc=inspect.getdoc(func),
        )

    def __extract_streaming_type(self, obj: object) -> t.Optional[TypeInfo]:
        origin = t.get_origin(obj)
        if not isinstance(origin, type) or not issubclass(origin, (t.Iterator, t.AsyncIterator)):
            return None

        args = t.get_args(obj)
        assert len(args) == 1

        return self.__inspector.inspect(args[0])

    def __build_param(self, param: inspect.Parameter) -> ParameterInfo:
        return ParameterInfo(
            name=param.name,
            type_=self.__inspector.inspect(param.annotation),
            default=Option(param.default) if param.default is not param.empty else Option[object].empty(),
        )
