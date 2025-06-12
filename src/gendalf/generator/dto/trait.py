import typing as t
from functools import cached_property

from astlab.abc import Expr, TypeRef
from astlab.builder import ClassBodyASTBuilder, ClassHeaderASTBuilder, ScopeASTBuilder
from astlab.types import NamedTypeInfo, TypeInfo

from gendalf._typing import override
from gendalf.generator.dto.abc import DtoMapperTrait

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


class PydanticDtoMapperTrait(DtoMapperTrait):
    def __init__(self, *, mode: t.Literal["python", "json"] = "json") -> None:
        self.__mode = mode

    @override
    def create_dto_class_def(self, scope: ScopeASTBuilder, name: str) -> ClassHeaderASTBuilder:
        return scope.class_def(name).inherits(self.__base_model)

    @override
    def add_dto_field_def(
        self,
        scope: ClassBodyASTBuilder,
        name: str,
        info: TypeRef,
        default: t.Optional[Expr] = None,
    ) -> None:
        scope.field_def(
            name=name,
            annotation=info,
            default=default,
        )

    @override
    def build_dto_decode_expr(self, scope: ScopeASTBuilder, dto: TypeRef, source: Expr) -> Expr:
        return scope.attr(dto, "model_validate_json" if self.__mode == "json" else "model_validate").call().arg(source)

    @override
    def build_dto_encode_expr(self, scope: ScopeASTBuilder, dto: TypeRef, source: Expr) -> Expr:
        return (
            scope.attr(source, "model_dump_json" if self.__mode == "json" else "model_dump")
            .call(kwargs={"mode": scope.const("json")} if self.__mode == "python" else None)
            .kwarg("by_alias", scope.const(value=True))
            .kwarg("exclude_none", scope.const(value=True))
        )

    @cached_property
    def __base_model(self) -> TypeInfo:
        return NamedTypeInfo.build("pydantic", "BaseModel")
