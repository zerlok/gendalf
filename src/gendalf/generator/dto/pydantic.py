import abc
import decimal
import inspect
import sys
import typing as t
import uuid
from dataclasses import dataclass, is_dataclass, replace
from dataclasses import fields as get_dataclass_fields
from datetime import date, datetime, time, timedelta
from functools import cached_property

from astlab.abc import Expr, TypeRef
from astlab.builder import AttrASTBuilder, Comprehension, ScopeASTBuilder, TypeRefBuilder
from astlab.types import (
    EnumTypeInfo,
    LiteralTypeInfo,
    ModuleInfo,
    NamedTypeInfo,
    RuntimeType,
    TypeAnnotator,
    TypeInfo,
    TypeInspector,
    TypeLoader,
    TypeVarInfo,
    UnionTypeInfo,
    predef,
)

from gendalf._typing import assert_never, override
from gendalf.generator.dto.abc import DtoMapper, DuplexDtoMapper
from gendalf.generator.dto.traverse import traverse_post_order

if sys.version_info >= (3, 12):
    from typing import TypeAliasType

else:
    TypeAliasType: t.Any = object()  # type: ignore[explicit-any]


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
class ProcessedDomainType:
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
    ) -> TypeRefBuilder: ...

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
            transform=self.__process_type,
            ancestors=self.__get_dependencies,
        ):
            self.__domain_to_dto[result.domain] = result.mapping_factory(scope)

    def __check_if_not_mapped(self, info: TypeInfo) -> bool:
        return info not in self.__domain_to_dto

    def __get_dependencies(self, options: ProcessedDomainType) -> t.Sequence[TypeInfo]:
        return options.dependencies

    # NOTE: ruff can't work with custom assert_never in this function
    def __process_type(self, info: TypeInfo) -> ProcessedDomainType:  # noqa: RET503
        rtt = self.__loader.load(info)

        if isinstance(info, NamedTypeInfo):
            return self.__process_named(rtt, info)

        elif isinstance(info, UnionTypeInfo):
            return self.__process_union(rtt, info)

        elif isinstance(info, TypeVarInfo):
            return self.__process_type_var(rtt, info)

        elif isinstance(info, EnumTypeInfo):
            return self.__process_enum(rtt, info)

        elif isinstance(info, LiteralTypeInfo):
            return self.__process_scalar(rtt, info)

        elif isinstance(info, ModuleInfo):
            msg = "module can't be a domain type"
            raise TypeError(msg, info)

        else:
            assert_never(info)

    def __process_named(self, rtt: RuntimeType, info: NamedTypeInfo) -> ProcessedDomainType:
        origin: object = t.get_origin(rtt)
        meta = type(rtt)

        if rtt in {None, Ellipsis}:
            return self.__process_const(rtt, info)

        if isinstance(rtt, type) and issubclass(rtt, self.__scalar_types):  # type: ignore[misc]
            return self.__process_scalar(rtt, info)

        if meta is TypeAliasType:  # type: ignore[misc]
            return self.__process_type_alias(rtt, info)

        if origin is t.Union:
            return self.__process_union(rtt, info)

        if isinstance(origin, type) and issubclass(origin, t.Container):  # type: ignore[misc]
            return self.__process_container(rtt, origin, info)

        return self.__process_structure(rtt, info)

    def __process_const(self, _: RuntimeType, info: TypeInfo) -> ProcessedDomainType:
        if info == predef().none:

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

        return ProcessedDomainType(
            domain=info,
            dependencies=[],
            mapping_factory=create,
        )

    def __process_scalar(self, _: RuntimeType, info: TypeInfo) -> ProcessedDomainType:
        def mapper(
            scope: ScopeASTBuilder,  # noqa: ARG001
            source: AttrASTBuilder,
            source_type: TypeInfo,  # noqa: ARG001
            target_type: TypeInfo,  # noqa: ARG001
        ) -> Expr:
            return source

        def create(_: ScopeASTBuilder) -> DomainTypeMapping:
            return DomainTypeMapping(dto=info, domain=info, mapper=mapper)

        return ProcessedDomainType(
            domain=info,
            dependencies=[],
            mapping_factory=create,
        )

    def __process_type_alias(self, rtt: RuntimeType, info: NamedTypeInfo) -> ProcessedDomainType:
        value: RuntimeType = getattr(rtt, "__value__", None)
        of_type = self.__inspector.inspect(value)

        def create(mod: ScopeASTBuilder) -> DomainTypeMapping:
            mapping = self.__domain_to_dto[of_type]

            with mod.type_alias(info.name) as type_alias:
                type_alias.assign(mapping.dto)

            def mapper(
                scope: ScopeASTBuilder,
                source: AttrASTBuilder,
                source_type: TypeInfo,
                target_type: TypeInfo,
            ) -> Expr:
                return mapping.mapper(
                    scope,
                    source,
                    of_type if source_type == info else mapping.dto,
                    of_type if target_type == info else mapping.dto,
                )

            return DomainTypeMapping(
                dto=type_alias.info,
                domain=info,
                mapper=mapper,
            )

        return ProcessedDomainType(
            domain=info,
            dependencies=[of_type],
            mapping_factory=create,
        )

    def __process_union(self, rtt: RuntimeType, info: t.Union[NamedTypeInfo, UnionTypeInfo]) -> ProcessedDomainType:
        values = self.__extract_nested(info)
        if len(values) == 2 and predef().none in values:  # noqa: PLR2004
            return self.__process_optional(rtt, info)

        def create(_: ScopeASTBuilder) -> DomainTypeMapping:
            value_mappings = [self.__domain_to_dto[val] for val in reversed(values)]
            dto_values = tuple(mapping.dto for mapping in reversed(value_mappings))

            def mapper(
                scope: ScopeASTBuilder,
                source: AttrASTBuilder,
                source_type: TypeInfo,
                target_type: TypeInfo,
            ) -> Expr:
                source_vals = list(reversed(self.__extract_nested(source_type)))
                target_vals = list(reversed(self.__extract_nested(target_type)))

                if not (len(value_mappings) == len(source_vals) == len(target_vals)):
                    msg = "source & target value amount mismatch"
                    raise ValueError(msg, value_mappings, source_vals, target_vals)

                node = value_mappings[0].mapper(scope, source, source_vals[0], target_vals[0])

                for mapping, source_val, target_val in zip(
                    value_mappings[1:],
                    source_vals[1:],
                    target_vals[1:],
                ):
                    node = scope.ternary_expr(
                        body=mapping.mapper(scope, source, source_val, target_val),
                        test=scope.attr("isinstance").call().arg(source).arg(scope.type_ref(source_val)),
                        or_else=node,
                    )

                return node

            return DomainTypeMapping(
                dto=self.__replace_nested(info, dto_values),
                domain=info,
                mapper=mapper,
            )

        return ProcessedDomainType(
            domain=info,
            dependencies=values,
            mapping_factory=create,
        )

    def __process_optional(self, rtt: RuntimeType, info: t.Union[NamedTypeInfo, UnionTypeInfo]) -> ProcessedDomainType:
        of_type = self.__extract_optional(info)

        def create(_: ScopeASTBuilder) -> DomainTypeMapping:
            mapping = self.__domain_to_dto[of_type]

            def mapper(
                scope: ScopeASTBuilder,
                source: AttrASTBuilder,
                source_type: TypeInfo,
                target_type: TypeInfo,
            ) -> Expr:
                return scope.ternary_not_none_expr(
                    body=mapping.mapper(
                        scope,
                        source,
                        self.__extract_optional(source_type),
                        self.__extract_optional(target_type),
                    ),
                    test=source,
                )

            return DomainTypeMapping(
                dto=self.__replace_nested(info, [mapping.dto]),
                domain=info,
                mapper=mapper,
            )

        return ProcessedDomainType(
            domain=info,
            dependencies=[of_type],
            mapping_factory=create,
        )

    def __process_container(
        self,
        rtt: RuntimeType,
        origin: type[object],
        info: NamedTypeInfo,
    ) -> ProcessedDomainType:
        if issubclass(origin, t.Mapping):

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                key_map, value_map = self.__get_nested_mappings(info)

                def mapper(
                    scope: ScopeASTBuilder,
                    source: AttrASTBuilder,
                    source_type: TypeInfo,
                    target_type: TypeInfo,
                ) -> Expr:
                    return scope.dict_expr(
                        items=Comprehension(
                            target=scope.tuple_expr(
                                self.__build_attr(scope, source, "key"),
                                self.__build_attr(scope, source, "value"),
                            ),
                            items=scope.attr(source, "items").call(),
                        ),
                        key=key_map.mapper(
                            scope=scope,
                            source=self.__build_attr(scope, source, "key"),
                            source_type=self.__extract_nested(source_type)[0],
                            target_type=self.__extract_nested(target_type)[0],
                        ),
                        value=value_map.mapper(
                            scope=scope,
                            source=self.__build_attr(scope, source, "value"),
                            source_type=self.__extract_nested(source_type)[1],
                            target_type=self.__extract_nested(target_type)[1],
                        ),
                    )

                return DomainTypeMapping(
                    dto=replace(info, type_params=(key_map.dto, value_map.dto)),
                    domain=info,
                    mapper=mapper,
                )

        elif issubclass(origin, t.Sequence):

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                (of_type,) = self.__get_nested_mappings(info)

                def mapper(
                    scope: ScopeASTBuilder,
                    source: AttrASTBuilder,
                    source_type: TypeInfo,
                    target_type: TypeInfo,
                ) -> Expr:
                    return scope.list_expr(
                        items=Comprehension(
                            target=self.__build_attr(scope, source, "item"),
                            items=source,
                        ),
                        element=of_type.mapper(
                            scope=scope,
                            source=self.__build_attr(scope, source, "item"),
                            source_type=self.__extract_nested(source_type)[0],
                            target_type=self.__extract_nested(target_type)[0],
                        ),
                    )

                return DomainTypeMapping(
                    dto=replace(info, type_params=(of_type.dto,)),
                    domain=info,
                    mapper=mapper,
                )

        elif issubclass(origin, t.Collection):

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                (of_type,) = self.__get_nested_mappings(info)

                def mapper(
                    scope: ScopeASTBuilder,
                    source: AttrASTBuilder,
                    source_type: TypeInfo,
                    target_type: TypeInfo,
                ) -> Expr:
                    return scope.set_expr(
                        items=Comprehension(
                            target=self.__build_attr(scope, source, "item"),
                            items=source,
                        ),
                        element=of_type.mapper(
                            scope=scope,
                            source=self.__build_attr(scope, source, "item"),
                            source_type=self.__extract_nested(source_type)[0],
                            target_type=self.__extract_nested(target_type)[0],
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

        return ProcessedDomainType(
            domain=info,
            dependencies=self.__extract_nested(info),
            mapping_factory=create,
        )

    # TODO: generic struct case
    def __process_structure(self, rtt: RuntimeType, info: NamedTypeInfo) -> ProcessedDomainType:
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

        return ProcessedDomainType(
            domain=info,
            dependencies=[annotation for _, annotation in fields],
            mapping_factory=create,
        )

    def __process_type_var(self, rtt: RuntimeType, info: TypeVarInfo) -> ProcessedDomainType:
        def create(_: ScopeASTBuilder) -> DomainTypeMapping:
            def mapper(
                scope: ScopeASTBuilder,
                source: AttrASTBuilder,
                source_type: TypeInfo,
                target_type: TypeInfo,
            ) -> Expr:
                # TODO: provide mapper interface that should be implemented and injected into mapping code
                return scope.call(scope.generic_type("__MAPPER__", source_type, target_type)).arg(source)

            return DomainTypeMapping(
                dto=info,
                domain=info,
                mapper=mapper,
            )

        return ProcessedDomainType(
            domain=info,
            dependencies=[],
            mapping_factory=create,
        )

    def __process_enum(self, rtt: RuntimeType, info: EnumTypeInfo) -> ProcessedDomainType:
        def create(mod: ScopeASTBuilder) -> DomainTypeMapping:
            with mod.type_alias(info.name) as type_alias:
                type_alias.assign(mod.literal_type(*(mod.const(val.value) for val in info.values)))

            # TODO: improve mapping for enum classes
            def mapper(
                scope: ScopeASTBuilder,  # noqa: ARG001
                source: AttrASTBuilder,
                source_type: TypeInfo,  # noqa: ARG001
                target_type: TypeInfo,  # noqa: ARG001
            ) -> Expr:
                return source

            return DomainTypeMapping(
                dto=info,
                domain=info,
                mapper=mapper,
            )

        return ProcessedDomainType(
            domain=info,
            dependencies=[],
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

    def __build_attr(self, scope: ScopeASTBuilder, source: AttrASTBuilder, *tail: str) -> AttrASTBuilder:
        return scope.attr("_".join((*source.parts, *tail)))

    def __extract_nested(self, info: TypeInfo) -> t.Sequence[TypeInfo]:
        if isinstance(info, NamedTypeInfo):
            if info.qualname == predef().optional.qualname:
                return *info.type_params, predef().none

            return info.type_params

        elif isinstance(info, UnionTypeInfo):
            return info.values

        else:
            return ()

    def __extract_optional(self, info: TypeInfo) -> TypeInfo:
        return next(
            typ
            for typ in (
                info.type_params
                if isinstance(info, NamedTypeInfo)
                else info.values
                if isinstance(info, UnionTypeInfo)
                else ()
            )
            if typ != predef().none
        )

    def __replace_nested(self, info: TypeInfo, nested: t.Sequence[TypeInfo]) -> TypeInfo:
        if isinstance(info, NamedTypeInfo):
            if info.qualname == predef().optional.qualname:
                return replace(info, type_params=(nested[0],))

            return replace(info, type_params=nested)

        elif isinstance(info, UnionTypeInfo):
            return replace(info, values=nested)

        else:
            return info

    def __get_nested_mappings(self, domain: t.Union[NamedTypeInfo, UnionTypeInfo]) -> t.Sequence[DomainTypeMapping]:
        return tuple(self.__domain_to_dto[typ] for typ in self.__extract_nested(domain))

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
