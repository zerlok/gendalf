import decimal
import inspect
import typing as t
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import cached_property

from astlab.abc import Expr, TypeRef
from astlab.builder import ScopeASTBuilder
from astlab.types import LiteralTypeInfo, NamedTypeInfo, RuntimeType, TypeInfo, TypeInspector, TypeLoader

from gendalf._typing import assert_never, override
from gendalf.generator.dto.abc import DtoMapper
from gendalf.generator.dto.traverse import traverse_post_order

# class DataclassDtoMapperTrait(DtoMapperTrait):
#     @override
#     def create_dto_class_def(self, scope: ScopeASTBuilder, name: str) -> ClassHeaderASTBuilder:
#         return scope.class_def(name).dataclass(
#             frozen=True,
#             kw_only=self.__is_kw_only_supported,
#         )
#
#     @cached_property
#     def __is_kw_only_supported(self) -> bool:
#         return sys.version_info >= (3, 10)


@dataclass(frozen=True)
class DomainTypeMapping:
    dto: TypeRef
    dto_to_domain: t.Callable[[Expr], Expr]
    domain_to_dto: t.Callable[[Expr], Expr]


@dataclass(frozen=True)
class ProcessedDomainTypeInfo:
    domain: TypeInfo
    dependencies: t.Sequence[RuntimeType]
    mapping_factory: t.Callable[[ScopeASTBuilder], DomainTypeMapping]


class PydanticDtoMapper(DtoMapper):
    def __init__(
        self,
        *,
        mode: t.Literal["python", "json"] = "json",
        loader: t.Optional[TypeLoader] = None,
        inspector: t.Optional[TypeInspector] = None,
    ) -> None:
        self.__mode = mode
        self.__loader = loader if loader is not None else TypeLoader()
        self.__inspector = inspector if inspector is not None else TypeInspector()
        self.__domain_to_dto = dict[TypeInfo, DomainTypeMapping]()

    @t.overload
    def create_dto_class_def(
        self,
        scope: ScopeASTBuilder,
        info: TypeInfo,
    ) -> TypeRef: ...

    @t.overload
    def create_dto_class_def(
        self,
        scope: ScopeASTBuilder,
        name: str,
        fields: t.Mapping[str, TypeInfo],
        doc: t.Optional[str] = None,
    ) -> TypeRef: ...

    @override
    def create_dto_class_def(
        self,
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

            with scope.class_def(name).inherits(self.__base_model) as class_def:
                for field, annotation in fields.items():
                    class_def.field_def(field, self.__domain_to_dto[annotation].dto)

            return class_def.ref()

        else:
            assert_never(info, name, fields)

    @override
    def build_dto_decode_expr(self, scope: ScopeASTBuilder, dto: TypeRef, source: Expr) -> Expr:
        return scope.attr(dto, "model_validate_json" if self.__mode == "json" else "model_validate").call().arg(source)

    def build_dto_to_domain_expr(self, scope: ScopeASTBuilder, dto: TypeRef, domain: TypeRef, source: Expr) -> Expr:
        return scope.const(value=f"{source} => {dto} -> {domain}")

    def build_domain_to_dto_expr(self, scope: ScopeASTBuilder, domain: TypeRef, dto: TypeRef, source: Expr) -> Expr:
        return scope.const(value=f"{source} => {domain} -> {dto}")

    @override
    def build_dto_encode_expr(self, scope: ScopeASTBuilder, dto: TypeRef, source: Expr) -> Expr:
        return (
            scope.attr(source, "model_dump_json" if self.__mode == "json" else "model_dump")
            .call(kwargs={"mode": scope.const("json")} if self.__mode == "python" else None)
            .kwarg("by_alias", scope.const(value=True))
            .kwarg("exclude_none", scope.const(value=True))
        )

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

    def __extract_dependencies(self, options: ProcessedDomainTypeInfo) -> t.Sequence[RuntimeType]:
        return options.dependencies

    def __process_domain_type(self, info: TypeInfo) -> ProcessedDomainTypeInfo:
        rtt = self.__loader.load(info)

        if isinstance(info, NamedTypeInfo):
            if rtt in {None, Ellipsis} or (isinstance(rtt, type) and issubclass(rtt, self.__scalar_types)):
                return self.__process_scalar(rtt, info)

            origin = t.get_origin(rtt)
            if origin is t.Union:
                return self.__process_union(rtt, info)

            if isinstance(origin, type):
                if issubclass(origin, t.Container):
                    return self.__process_container(rtt, info)

                else:
                    raise NotImplementedError(rtt, origin)

            return self.__process_structure(rtt, info)

        elif isinstance(info, LiteralTypeInfo):
            return self.__process_scalar(rtt, info)

        else:
            assert_never(info)

    def __process_scalar(self, rtt: RuntimeType, info: TypeInfo) -> ProcessedDomainTypeInfo:
        def create(_: ScopeASTBuilder) -> DomainTypeMapping:
            return DomainTypeMapping(
                dto=rtt,
                dto_to_domain=lambda x: x,
                domain_to_dto=lambda x: x,
            )

        return ProcessedDomainTypeInfo(
            domain=info,
            dependencies=[],
            mapping_factory=create,
        )

    def __process_union(self, rtt: RuntimeType, info: TypeInfo) -> ProcessedDomainTypeInfo:
        def create(scope: ScopeASTBuilder) -> DomainTypeMapping:
            return DomainTypeMapping(
                dto=rtt,
                dto_to_domain=lambda x: x.ternary_not_none_expr(x, x),
                domain_to_dto=lambda x: x.ternary_not_none_expr(x, x),
            )

        return ProcessedDomainTypeInfo(
            domain=info,
            dependencies=self.__inspect_generic_args(rtt),
            mapping_factory=create,
        )

    def __process_container(self, rtt: RuntimeType, info: TypeInfo) -> ProcessedDomainTypeInfo:
        if issubclass(rtt, t.Mapping):

            def create(scope: ScopeASTBuilder) -> DomainTypeMapping:
                return DomainTypeMapping(
                    dto=rtt,
                    dto_to_domain=lambda x: x.dict_expr({"dto-to-domain": "yes"}),
                    domain_to_dto=lambda x: x.dict_expr({"domain-to-dto": "yes"}),
                )

        elif issubclass(rtt, t.Sequence):

            def create(scope: ScopeASTBuilder) -> DomainTypeMapping:
                return DomainTypeMapping(
                    dto=rtt,
                    dto_to_domain=lambda x: x.list_expr(["dto-to-domain"]),
                    domain_to_dto=lambda x: x.list_expr(["domain-to-dto"]),
                )

        else:

            def create(scope: ScopeASTBuilder) -> DomainTypeMapping:
                return DomainTypeMapping(
                    dto=rtt,
                    dto_to_domain=lambda x: x.set_expr({"dto-to-domain"}),
                    domain_to_dto=lambda x: x.set_expr({"domain-to-dto"}),
                )

        return ProcessedDomainTypeInfo(
            domain=info,
            dependencies=self.__inspect_generic_args(rtt),
            mapping_factory=create,
        )

    def __process_structure(self, rtt: RuntimeType, info: TypeInfo) -> ProcessedDomainTypeInfo:
        members = [(field, annotation) for field, annotation in inspect.getmembers(rtt) if not field.startswith("_")]

        def create(scope: ScopeASTBuilder) -> TypeRef:
            with (
                scope.class_def(info.name)
                .inherits(self.__base_model)
                .docstring(f"DTO for `{info.qualname}` type") as class_def
            ):
                for field, annotation in members:
                    class_def.field_def(field, self.__domain_to_dto[annotation].dto)

            return DomainTypeMapping(
                dto=class_def,
                dto_to_domain=lambda x: class_def.call().kwarg("field", x.attr("field")),
                domain_to_dto=lambda x: class_def.call().kwarg("field", x.attr("field")),
            )

        return ProcessedDomainTypeInfo(
            domain=info,
            dependencies=[*self.__inspect_generic_args(rtt), *(annotation for _, annotation in members)],
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

    def __inspect_generic_args(self, rtt: RuntimeType) -> t.Sequence[TypeInfo]:
        args = t.get_args(rtt)
        return [self.__inspector.inspect(arg) for arg in args] if args is not None else []
