import abc
import decimal
import inspect
import typing as t
import uuid
from dataclasses import dataclass, is_dataclass, replace
from dataclasses import fields as get_dataclass_fields
from datetime import date, datetime, time, timedelta
from functools import cached_property

from astlab.abc import Expr, TypeRef
from astlab.builder import AttrASTBuilder, ClassTypeRefBuilder, Comprehension, ScopeASTBuilder
from astlab.types import (
    LiteralTypeInfo,
    ModuleInfo,
    NamedTypeInfo,
    RuntimeType,
    TypeAnnotator,
    TypeInfo,
    TypeInspector,
    TypeLoader,
    predef,
)

from gendalf._typing import assert_never, override
from gendalf.generator.dto.abc import DtoMapper, DuplexDtoMapper
from gendalf.generator.dto.traverse import traverse_post_order

if t.TYPE_CHECKING:
    from dataclasses import Field


PydanticMode = t.Literal["python", "serializable", "json"]


class MapperFunc(t.Protocol):
    @abc.abstractmethod
    def __call__(
        self,
        scope: ScopeASTBuilder,
        source: AttrASTBuilder,
        source_type: TypeInfo,
        target_type: TypeInfo,
    ) -> Expr:
        raise NotImplementedError


@dataclass(frozen=True)
class DomainTypeMapping:
    dto: TypeInfo
    domain: TypeInfo
    mapper: MapperFunc


@dataclass(frozen=True)
class ProcessedDomainTypeInfo:
    domain: TypeInfo
    dependencies: t.Sequence[TypeInfo]
    mapping_factory: t.Callable[[ScopeASTBuilder], DomainTypeMapping]


class PydanticDtoMapper(DtoMapper):
    def __init__(
        self,
        *,
        mode: PydanticMode = "json",
        loader: t.Optional[TypeLoader] = None,
        inspector: t.Optional[TypeInspector] = None,
        annotator: t.Optional[TypeAnnotator] = None,
    ) -> None:
        self.__loader = loader if loader is not None else TypeLoader()
        self.__inspector = inspector if inspector is not None else TypeInspector()
        self.__annotator = annotator if annotator is not None else TypeAnnotator()
        self.__domain_to_dto = dict[TypeInfo, DomainTypeMapping]()
        self.__mapper = PydanticDuplexDtoMapper(self.__domain_to_dto, mode)

    @t.overload
    def create_dto_def(
        self,
        *,
        scope: ScopeASTBuilder,
        info: TypeInfo,
    ) -> TypeRef: ...

    @t.overload
    def create_dto_def(
        self,
        *,
        scope: ScopeASTBuilder,
        name: str,
        fields: t.Mapping[str, TypeInfo],
        doc: t.Optional[str] = None,
    ) -> ClassTypeRefBuilder: ...

    @override
    def create_dto_def(
        self,
        *,
        scope: ScopeASTBuilder,
        info: t.Optional[TypeInfo] = None,
        name: t.Optional[str] = None,
        fields: t.Optional[t.Mapping[str, TypeInfo]] = None,
        doc: t.Optional[str] = None,
    ) -> TypeRef:
        if info is not None:
            self.__build_type_mapping(scope, [info])
            return self.__domain_to_dto[info].dto

        elif name is not None and fields is not None:
            self.__build_type_mapping(scope, list(fields.values()))

            with scope.class_def(name).inherits(self.__base_model).docstring(doc) as class_def:
                for field, annotation in fields.items():
                    class_def.field_def(field, self.__domain_to_dto[annotation].dto)

            return class_def.ref()

        else:
            raise RuntimeError(info, name, fields)

    def mode(self, value: t.Optional[PydanticMode]) -> DuplexDtoMapper:
        return (
            PydanticDuplexDtoMapper(self.__domain_to_dto, value)
            if value is not None and value != self.__mapper.mode
            else self.__mapper
        )

    @override
    def build_dto_decode_expr(self, scope: ScopeASTBuilder, dto: TypeInfo, source: Expr) -> Expr:
        return self.__mapper.build_dto_encode_expr(scope, dto, source)

    @override
    def build_dto_to_domain_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: AttrASTBuilder) -> Expr:
        return self.__mapper.build_dto_to_domain_expr(scope, domain, source)

    @override
    def build_domain_to_dto_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: AttrASTBuilder) -> Expr:
        return self.__mapper.build_domain_to_dto_expr(scope, domain, source)

    @override
    def build_dto_encode_expr(self, scope: ScopeASTBuilder, dto: TypeInfo, source: Expr) -> Expr:
        return self.__mapper.build_dto_encode_expr(scope, dto, source)

    def __build_type_mapping(self, scope: ScopeASTBuilder, infos: t.Sequence[TypeInfo]) -> None:
        for result in traverse_post_order(
            nodes=infos,
            predicate=self.__check_if_not_mapped,
            transform=self.__process_domain_type,
            ancestors=self.__extract_dependencies,
        ):
            self.__domain_to_dto[result.domain] = result.mapping_factory(scope)

    def __check_if_not_mapped(self, info: TypeInfo) -> bool:
        return info not in self.__domain_to_dto

    def __extract_dependencies(self, options: ProcessedDomainTypeInfo) -> t.Sequence[TypeInfo]:
        return options.dependencies

    # NOTE: ruff can't work with custom assert_never in this function
    def __process_domain_type(self, info: TypeInfo) -> ProcessedDomainTypeInfo:  # noqa: RET503
        rtt = self.__loader.load(info)

        if isinstance(info, NamedTypeInfo):
            if rtt in {None, Ellipsis}:
                return self.__process_const(rtt, info)

            if isinstance(rtt, type) and issubclass(rtt, self.__scalar_types):  # type: ignore[misc]
                return self.__process_scalar(rtt, info)

            origin: object = t.get_origin(rtt)
            if origin is t.Union:
                return self.__process_union(rtt, info)

            if isinstance(origin, type) and issubclass(origin, t.Container):  # type: ignore[misc]
                return self.__process_container(rtt, origin, info)

            return self.__process_structure(rtt, info)

        elif isinstance(info, LiteralTypeInfo):
            return self.__process_scalar(rtt, info)

        elif isinstance(info, ModuleInfo):
            msg = "module can't be a domain type"
            raise TypeError(msg, info)

        else:
            assert_never(info)

    def __process_const(self, _: RuntimeType, info: TypeInfo) -> ProcessedDomainTypeInfo:
        if info == predef().none_type:

            def mapper(
                scope: ScopeASTBuilder,
                source: AttrASTBuilder,  # noqa: ARG001
                source_type: TypeInfo,  # noqa: ARG001
                target_type: TypeInfo,  # noqa: ARG001
            ) -> Expr:
                return scope.none()

        elif info == predef().ellipsis:

            def mapper(
                scope: ScopeASTBuilder,
                source: AttrASTBuilder,  # noqa: ARG001
                source_type: TypeInfo,  # noqa: ARG001
                target_type: TypeInfo,  # noqa: ARG001
            ) -> Expr:
                return scope.ellipsis()

        else:
            msg = "constant is not supported for this type"
            raise ValueError(msg, info)

        def create(_: ScopeASTBuilder) -> DomainTypeMapping:
            return DomainTypeMapping(dto=info, domain=info, mapper=mapper)

        return ProcessedDomainTypeInfo(
            domain=info,
            dependencies=[],
            mapping_factory=create,
        )

    def __process_scalar(self, _: RuntimeType, info: TypeInfo) -> ProcessedDomainTypeInfo:
        def mapper(
            scope: ScopeASTBuilder,  # noqa: ARG001
            source: AttrASTBuilder,
            source_type: TypeInfo,  # noqa: ARG001
            target_type: TypeInfo,  # noqa: ARG001
        ) -> Expr:
            return source

        def create(_: ScopeASTBuilder) -> DomainTypeMapping:
            return DomainTypeMapping(dto=info, domain=info, mapper=mapper)

        return ProcessedDomainTypeInfo(
            domain=info,
            dependencies=[],
            mapping_factory=create,
        )

    def __process_union(self, rtt: RuntimeType, info: NamedTypeInfo) -> ProcessedDomainTypeInfo:
        if info.qualname == predef().optional.qualname:

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                (type_param,) = self.__get_type_param_maps(info)

                def mapper(
                    scope: ScopeASTBuilder,
                    source: AttrASTBuilder,
                    source_type: TypeInfo,
                    target_type: TypeInfo,
                ) -> Expr:
                    return scope.ternary_not_none_expr(
                        body=type_param.mapper(
                            scope=scope,
                            source=source,
                            source_type=self.__extract_type_params(source_type)[0],
                            target_type=self.__extract_type_params(target_type)[0],
                        ),
                        test=source,
                    )

                return DomainTypeMapping(
                    dto=replace(info, type_params=(type_param.dto,)),
                    domain=info,
                    mapper=mapper,
                )

        else:

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                type_params = list(reversed(self.__get_type_param_maps(info)))

                def mapper(
                    scope: ScopeASTBuilder,
                    source: AttrASTBuilder,
                    source_type: TypeInfo,
                    target_type: TypeInfo,
                ) -> Expr:
                    source_type_params = list(reversed(self.__extract_type_params(source_type)))
                    target_type_params = list(reversed(self.__extract_type_params(target_type)))

                    node = type_params[0].mapper(scope, source, source_type_params[0], target_type_params[0])

                    for type_param, source_type_param, target_type_param in zip(
                        type_params[1:],
                        source_type_params[1:],
                        target_type_params[1:],
                    ):
                        node = scope.ternary_expr(
                            body=type_param.mapper(scope, source, source_type_param, target_type_param),
                            test=scope.attr("isinstance").call().arg(source).arg(scope.type_ref(source_type_param)),
                            or_else=node,
                        )

                    return node

                return DomainTypeMapping(
                    dto=replace(info, type_params=tuple(mapping.dto for mapping in self.__get_type_param_maps(info))),
                    domain=info,
                    mapper=mapper,
                )

        return ProcessedDomainTypeInfo(
            domain=info,
            dependencies=self.__inspect_type_params(rtt),
            mapping_factory=create,
        )

    # TODO: implement mapping
    def __process_container(
        self,
        rtt: RuntimeType,
        origin: type[object],
        info: NamedTypeInfo,
    ) -> ProcessedDomainTypeInfo:
        if issubclass(origin, t.Mapping):

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                key_map, value_map = self.__get_type_param_maps(info)

                def mapper(
                    scope: ScopeASTBuilder,
                    source: AttrASTBuilder,
                    source_type: TypeInfo,
                    target_type: TypeInfo,
                ) -> Expr:
                    return scope.dict_expr(
                        items=Comprehension(
                            target=scope.tuple_expr(
                                self.__build_attr_chain(scope, source, "key"),
                                self.__build_attr_chain(scope, source, "value"),
                            ),
                            items=scope.attr(source, "items").call(),
                        ),
                        key=key_map.mapper(
                            scope=scope,
                            source=self.__build_attr_chain(scope, source, "key"),
                            source_type=self.__extract_type_params(source_type)[0],
                            target_type=self.__extract_type_params(target_type)[0],
                        ),
                        value=value_map.mapper(
                            scope=scope,
                            source=self.__build_attr_chain(scope, source, "value"),
                            source_type=self.__extract_type_params(source_type)[1],
                            target_type=self.__extract_type_params(target_type)[1],
                        ),
                    )

                return DomainTypeMapping(
                    dto=replace(info, type_params=(key_map.dto, value_map.dto)),
                    domain=info,
                    mapper=mapper,
                )

        elif issubclass(origin, t.Sequence):

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                (of_type,) = self.__get_type_param_maps(info)

                def mapper(
                    scope: ScopeASTBuilder,
                    source: AttrASTBuilder,
                    source_type: TypeInfo,
                    target_type: TypeInfo,
                ) -> Expr:
                    return scope.list_expr(
                        items=Comprehension(
                            target=self.__build_attr_chain(scope, source, "item"),
                            items=source,
                        ),
                        element=of_type.mapper(
                            scope=scope,
                            source=self.__build_attr_chain(scope, source, "item"),
                            source_type=self.__extract_type_params(source_type)[0],
                            target_type=self.__extract_type_params(target_type)[0],
                        ),
                    )

                return DomainTypeMapping(
                    dto=replace(info, type_params=(of_type.dto,)),
                    domain=info,
                    mapper=mapper,
                )

        elif issubclass(origin, t.Collection):

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                (of_type,) = self.__get_type_param_maps(info)

                def mapper(
                    scope: ScopeASTBuilder,
                    source: AttrASTBuilder,
                    source_type: TypeInfo,
                    target_type: TypeInfo,
                ) -> Expr:
                    return scope.set_expr(
                        items=Comprehension(
                            target=self.__build_attr_chain(scope, source, "item"),
                            items=source,
                        ),
                        element=of_type.mapper(
                            scope=scope,
                            source=self.__build_attr_chain(scope, source, "item"),
                            source_type=self.__extract_type_params(source_type)[0],
                            target_type=self.__extract_type_params(target_type)[0],
                        ),
                    )

                return DomainTypeMapping(
                    dto=replace(info, type_params=(of_type.dto,)),
                    domain=info,
                    mapper=mapper,
                )

        else:
            # TODO: check for more container cases
            raise NotImplementedError(rtt, info)

        return ProcessedDomainTypeInfo(
            domain=info,
            dependencies=self.__inspect_type_params(rtt),
            mapping_factory=create,
        )

    # TODO: generic struct case
    def __process_structure(self, rtt: RuntimeType, info: NamedTypeInfo) -> ProcessedDomainTypeInfo:
        fields = self.__extract_fields(rtt)

        def create(mod: ScopeASTBuilder) -> DomainTypeMapping:
            field_mappings = {name: self.__domain_to_dto[annotation] for name, annotation in fields}

            with (
                mod.class_def(info.name)
                .inherits(self.__base_model)
                .docstring(f"DTO for :class:`{info.qualname}` type.") as class_def
            ):
                for name, mapping in field_mappings.items():
                    class_def.field_def(name, mapping.dto)

            def get_field_type(source_type: TypeInfo, name: str) -> TypeInfo:
                return field_mappings[name].domain if source_type == info else field_mappings[name].dto

            def mapper(
                scope: ScopeASTBuilder,
                source: AttrASTBuilder,
                source_type: TypeInfo,
                target_type: TypeInfo,
            ) -> Expr:
                return scope.call(
                    func=target_type,
                    kwargs={
                        name: field_map.mapper(
                            scope=scope,
                            source=scope.attr(source, name),
                            source_type=get_field_type(source_type, name),
                            target_type=get_field_type(target_type, name),
                        )
                        for name, field_map in field_mappings.items()
                    },
                )

            return DomainTypeMapping(
                dto=class_def.info,
                domain=info,
                mapper=mapper,
            )

        return ProcessedDomainTypeInfo(
            domain=info,
            dependencies=[annotation for _, annotation in fields],
            mapping_factory=create,
        )

    @cached_property
    def __base_model(self) -> TypeInfo:
        return NamedTypeInfo.build("pydantic", "BaseModel")

    @cached_property
    def __scalar_types(self) -> tuple[type[object], ...]:
        return (
            bool,
            int,
            float,
            complex,
            decimal.Decimal,
            bytes,
            str,
            uuid.UUID,
            date,
            time,
            datetime,
            timedelta,
        )

    def __inspect_type_params(self, rtt: RuntimeType) -> t.Sequence[TypeInfo]:
        args: t.Optional[t.Sequence[RuntimeType]] = t.get_args(rtt)
        return [self.__inspector.inspect(arg) for arg in args] if args is not None else []

    def __get_type_param_maps(self, domain: NamedTypeInfo) -> t.Sequence[DomainTypeMapping]:
        return tuple(self.__domain_to_dto[tp] for tp in domain.type_params)

    def __build_attr_chain(self, scope: ScopeASTBuilder, source: AttrASTBuilder, *tail: str) -> AttrASTBuilder:
        return scope.attr("_".join((*source.parts, *tail)))

    def __extract_type_params(self, info: TypeInfo) -> t.Sequence[TypeInfo]:
        if not isinstance(info, NamedTypeInfo):
            msg = "can't extract type params from non named type info"
            raise TypeError(msg, info)

        return info.type_params

    def __extract_fields(self, rtt: RuntimeType) -> t.Sequence[tuple[str, TypeInfo]]:
        if is_dataclass(rtt):
            # TODO: solve dataclass field forward ref
            return [
                (
                    field.name,
                    self.__inspector.inspect(t.cast("RuntimeType", field.type))
                    if not isinstance(t.cast("object", field.type), str)
                    else self.__annotator.parse(t.cast("str", field.type)),
                )
                for field in t.cast("t.Sequence[Field[type[object]]]", get_dataclass_fields(rtt))
            ]

        # TODO: include properties & check member inheritance
        return [
            (field, self.__inspector.inspect(annotation))
            for field, annotation in t.cast("t.Sequence[tuple[str, RuntimeType]]", inspect.getmembers(rtt))
            if not field.startswith("_")
        ]


class PydanticDuplexDtoMapper(DuplexDtoMapper):
    def __init__(self, registry: t.Mapping[TypeInfo, DomainTypeMapping], mode: PydanticMode) -> None:
        self.__registry = registry
        self.__mode = mode

    @property
    def mode(self) -> PydanticMode:
        return self.__mode

    @override
    def build_dto_decode_expr(self, scope: ScopeASTBuilder, dto: TypeInfo, source: Expr) -> Expr:
        return scope.attr(dto, "model_validate_json" if self.__mode == "json" else "model_validate").call().arg(source)

    @override
    def build_dto_to_domain_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: AttrASTBuilder) -> Expr:
        mapping = self.__registry[domain]
        return mapping.mapper(scope, source, mapping.dto, mapping.domain)

    @override
    def build_domain_to_dto_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: AttrASTBuilder) -> Expr:
        mapping = self.__registry[domain]
        return mapping.mapper(scope, source, mapping.domain, mapping.dto)

    @override
    def build_dto_encode_expr(self, scope: ScopeASTBuilder, dto: TypeInfo, source: Expr) -> Expr:
        return (
            scope.attr(source, "model_dump_json" if self.__mode == "json" else "model_dump")
            .call(kwargs={"mode": scope.const("json")} if self.__mode == "serializable" else None)
            .kwarg("by_alias", scope.const(value=True))
            .kwarg("exclude_none", scope.const(value=True))
        )
