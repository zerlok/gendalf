import decimal
import inspect
import typing as t
import uuid
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import date, datetime, time, timedelta
from functools import cached_property

from astlab.abc import Expr, TypeRef
from astlab.builder import ClassTypeRefBuilder, Comprehension, ScopeASTBuilder
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


@dataclass(frozen=True)
class DomainTypeMapping:
    dto: TypeInfo
    dto_to_domain: t.Callable[[ScopeASTBuilder, TypeRef, TypeRef, Expr], Expr]
    domain_to_dto: t.Callable[[ScopeASTBuilder, TypeRef, TypeRef, Expr], Expr]


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
    def build_dto_decode_expr(self, scope: ScopeASTBuilder, dto: TypeRef, source: Expr) -> Expr:
        return self.__mapper.build_dto_encode_expr(scope, dto, source)

    @override
    def build_dto_to_domain_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: Expr) -> Expr:
        return self.__mapper.build_dto_to_domain_expr(scope, domain, source)

    @override
    def build_domain_to_dto_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: Expr) -> Expr:
        return self.__mapper.build_domain_to_dto_expr(scope, domain, source)

    @override
    def build_dto_encode_expr(self, scope: ScopeASTBuilder, dto: TypeRef, source: Expr) -> Expr:
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
            if rtt in {None, Ellipsis} or (isinstance(rtt, type) and issubclass(rtt, self.__scalar_types)):  # type: ignore[misc]
                return self.__process_scalar(rtt, info)

            origin: object = t.get_origin(rtt)
            if origin is t.Union:
                return self.__process_union(rtt, info)

            if isinstance(rtt, type) and isinstance(origin, type):  # type: ignore[misc]
                if issubclass(origin, t.Container):
                    return self.__process_container(rtt, info)

                else:
                    # TODO: check for more container cases.
                    raise NotImplementedError(rtt, origin)

            return self.__process_structure(rtt, info)

        elif isinstance(info, LiteralTypeInfo):
            return self.__process_scalar(rtt, info)

        elif isinstance(info, ModuleInfo):
            msg = "module can't be a domain type"
            raise TypeError(msg, info)

        else:
            assert_never(info)

    def __process_scalar(self, _: RuntimeType, info: TypeInfo) -> ProcessedDomainTypeInfo:
        def create(_: ScopeASTBuilder) -> DomainTypeMapping:
            return DomainTypeMapping(
                dto=info,
                dto_to_domain=self.__build_ident_map,
                domain_to_dto=self.__build_ident_map,
            )

        return ProcessedDomainTypeInfo(
            domain=info,
            dependencies=[],
            mapping_factory=create,
        )

    def __process_union(self, rtt: RuntimeType, info: NamedTypeInfo) -> ProcessedDomainTypeInfo:
        if info.qualname == predef().optional.qualname:

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                (of_type,) = self.__get_type_param_maps(info)

                def mapper(scope: ScopeASTBuilder, source_type: TypeRef, _: TypeRef, source: Expr) -> Expr:
                    return scope.ternary_not_none_expr(
                        body=of_type.dto_to_domain(scope, source_type, of_type.dto, source),
                        test=source,
                    )

                return DomainTypeMapping(
                    dto=replace(info, type_params=(of_type.dto,)),
                    dto_to_domain=mapper,
                    domain_to_dto=mapper,
                )

        else:
            # TODO: isinstance for each union item
            raise NotImplementedError(rtt, info)

        return ProcessedDomainTypeInfo(
            domain=info,
            dependencies=self.__inspect_type_params(rtt),
            mapping_factory=create,
        )

    # TODO: implement mapping
    def __process_container(self, rtt: type[object], info: NamedTypeInfo) -> ProcessedDomainTypeInfo:
        if issubclass(rtt, t.Mapping):

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                key_type, value_type = self.__get_type_param_maps(info)

                def mapper(scope: ScopeASTBuilder, source_type: TypeRef, target_type: TypeRef, source: Expr) -> Expr:
                    return scope.dict_expr(
                        items=Comprehension(
                            target=scope.tuple_expr(scope.attr("key"), scope.attr("value")),
                            items=scope.attr(source, "items").call(),
                        ),
                        key=key_type.dto_to_domain(scope, source_type, target_type, scope.attr("key")),
                        value=value_type.dto_to_domain(scope, source_type, target_type, scope.attr("value")),
                    )

                return DomainTypeMapping(
                    dto=replace(info, type_params=(key_type.dto, value_type.dto)),
                    dto_to_domain=mapper,
                    domain_to_dto=mapper,
                )

        elif issubclass(rtt, t.Sequence):

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                (of_type,) = self.__get_type_param_maps(info)

                def mapper(scope: ScopeASTBuilder, _: TypeRef, __: TypeRef, source: Expr) -> Expr:
                    return scope.list_expr(
                        items=Comprehension(
                            target=scope.attr("item"),
                            items=scope.attr(source, "items").call(),
                        ),
                        element=of_type.dto_to_domain(scope, ..., of_type.dto, scope.attr("item")),
                    )

                return DomainTypeMapping(
                    dto=replace(info, type_params=(of_type.dto,)),
                    dto_to_domain=mapper,
                    domain_to_dto=mapper,
                )

        elif issubclass(rtt, t.Collection):

            def create(_: ScopeASTBuilder) -> DomainTypeMapping:
                (of_type,) = self.__get_type_param_maps(info)

                def mapper(scope: ScopeASTBuilder, _: TypeRef, __: TypeRef, source: Expr) -> Expr:
                    return scope.set_expr(
                        items=Comprehension(
                            target=scope.attr("item"),
                            items=scope.attr(source, "items").call(),
                        ),
                        element=of_type.dto_to_domain(scope, ..., of_type.dto, scope.attr("item")),
                    )

                return DomainTypeMapping(
                    dto=replace(info, type_params=(of_type.dto,)),
                    dto_to_domain=mapper,
                    domain_to_dto=mapper,
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

        def create(scope: ScopeASTBuilder) -> DomainTypeMapping:
            field_mappers = {name: self.__domain_to_dto[annotation] for name, annotation in fields}

            with (
                scope.class_def(info.name)
                .inherits(self.__base_model)
                .docstring(f"DTO for :class:`{info.qualname}` type.") as class_def
            ):
                for name, annotation in fields:
                    class_def.field_def(name, self.__domain_to_dto[annotation].dto)

            def mapper(map_scope: ScopeASTBuilder, source_ref: TypeRef, target_ref: TypeRef, source: Expr) -> Expr:
                return map_scope.call(
                    target_ref,
                    kwargs={
                        name: field_mappers[name].domain_to_dto(
                            map_scope,
                            source_ref,
                            target_ref,
                            map_scope.attr(source, name),
                        )
                        for name, _ in fields
                    },
                )

            return DomainTypeMapping(
                dto=class_def.info,
                dto_to_domain=mapper,
                domain_to_dto=mapper,
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
        return [self.__domain_to_dto[tp] for tp in domain.type_params]

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
                for field in t.cast("t.Sequence[Field[type[object]]]", fields(rtt))
            ]

        # TODO: include properties & check member inheritance
        return [
            (field, self.__inspector.inspect(annotation))
            for field, annotation in t.cast("t.Sequence[tuple[str, RuntimeType]]", inspect.getmembers(rtt))
            if not field.startswith("_")
        ]

    def __build_ident_map(
        self,
        map_scope: ScopeASTBuilder,
        source_type: TypeRef,
        target_type: TypeRef,
        source: Expr,
    ) -> Expr:
        return source


class PydanticDuplexDtoMapper(DuplexDtoMapper):
    def __init__(self, registry: t.Mapping[TypeInfo, DomainTypeMapping], mode: PydanticMode) -> None:
        self.__registry = registry
        self.__mode = mode

    @property
    def mode(self) -> PydanticMode:
        return self.__mode

    @override
    def build_dto_decode_expr(
        self,
        scope: ScopeASTBuilder,
        dto: TypeRef,
        source: Expr,
    ) -> Expr:
        return scope.attr(dto, "model_validate_json" if self.__mode == "json" else "model_validate").call().arg(source)

    @override
    def build_dto_to_domain_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: Expr) -> Expr:
        mapping = self.__registry[domain]
        return mapping.dto_to_domain(scope, mapping.dto, domain, source)

    @override
    def build_domain_to_dto_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: Expr) -> Expr:
        mapping = self.__registry[domain]
        return mapping.domain_to_dto(scope, domain, mapping.dto, source)

    @override
    def build_dto_encode_expr(
        self,
        scope: ScopeASTBuilder,
        dto: TypeRef,
        source: Expr,
    ) -> Expr:
        return (
            scope.attr(source, "model_dump_json" if self.__mode == "json" else "model_dump")
            .call(kwargs={"mode": scope.const("json")} if self.__mode == "serializable" else None)
            .kwarg("by_alias", scope.const(value=True))
            .kwarg("exclude_none", scope.const(value=True))
        )
