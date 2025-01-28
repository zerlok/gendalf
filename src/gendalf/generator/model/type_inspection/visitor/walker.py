import typing as t

from gendalf._typing import assert_never, override
from gendalf.generator.model.type_inspection.visitor.abc import TypeVisitor, TypeVisitorDecorator, TypeWalkerTrait
from gendalf.generator.model.type_inspection.visitor.model import (
    ContainerContext,
    EnumContext,
    EnumValueContext,
    ScalarContext,
    StructureContext,
    StructureFieldContext,
)

T_contra = t.TypeVar("T_contra", contravariant=True)


class TypeWalker(TypeVisitor[T_contra]):
    def __init__(
        self,
        trait: TypeWalkerTrait,
        *nested: TypeVisitorDecorator[T_contra],
    ) -> None:
        self.__trait = trait
        self.__nested = nested

    @override
    def visit_scalar(self, context: ScalarContext, meta: T_contra) -> None:
        for nested in self.__nested:
            nested.enter_scalar(context, meta)

        for nested in reversed(self.__nested):
            nested.leave_scalar(context, meta)

    @override
    def visit_enum(self, context: EnumContext, meta: T_contra) -> None:
        for nested in self.__nested:
            nested.enter_enum(context, meta)

        for value in context.values:
            self.visit_enum_value(value, meta)

        for nested in reversed(self.__nested):
            nested.leave_enum(context, meta)

    @override
    def visit_enum_value(self, context: EnumValueContext, meta: T_contra) -> None:
        for nested in self.__nested:
            nested.enter_enum_value(context, meta)

        for nested in reversed(self.__nested):
            nested.leave_enum_value(context, meta)

    @override
    def visit_container(self, context: ContainerContext, meta: T_contra) -> None:
        for nested in self.__nested:
            nested.enter_container(context, meta)

        for inner in context.inners:
            self.walk(inner, meta)

        for nested in reversed(self.__nested):
            nested.leave_container(context, meta)

    @override
    def visit_structure(self, context: StructureContext, meta: T_contra) -> None:
        for nested in self.__nested:
            nested.enter_structure(context, meta)

        for field in context.fields:
            self.visit_structure_field(field, meta)

        for nested in reversed(self.__nested):
            nested.leave_structure(context, meta)

    @override
    def visit_structure_field(self, context: StructureFieldContext, meta: T_contra) -> None:
        for nested in self.__nested:
            nested.enter_structure_field(context, meta)

        self.walk(context.annotation, meta)

        for nested in reversed(self.__nested):
            nested.leave_structure_field(context, meta)

    def walk(self, type_: t.Optional[type[object]], meta: T_contra) -> None:
        ctx = self.__trait.extract(type_)

        if isinstance(ctx, ScalarContext):
            self.visit_scalar(ctx, meta)

        elif isinstance(ctx, EnumContext):
            self.visit_enum(ctx, meta)

        elif isinstance(ctx, EnumValueContext):
            self.visit_enum_value(ctx, meta)

        elif isinstance(ctx, ContainerContext):
            self.visit_container(ctx, meta)

        elif isinstance(ctx, StructureContext):
            self.visit_structure(ctx, meta)

        elif isinstance(ctx, StructureFieldContext):
            self.visit_structure_field(ctx, meta)

        elif ctx is None:
            details = "unsupported type"
            raise TypeError(details, type_, meta)

        else:
            assert_never(ctx)
