import typing as t
from collections import deque
from dataclasses import dataclass

from astlab.abc import Expr, TypeRef
from astlab.builder import AttrASTBuilder, ClassRefBuilder, ModuleASTBuilder, ScopeASTBuilder
from astlab.info import TypeInfo

from gendalf._typing import override
from gendalf.generator.model.abc import ModelFactory
from gendalf.generator.model.type_inspection.visitor.abc import TypeVisitorDecorator, TypeWalkerTrait
from gendalf.generator.model.type_inspection.visitor.model import (
    ContainerContext,
    EnumContext,
    EnumValueContext,
    ScalarContext,
    StructureContext,
    StructureFieldContext,
)
from gendalf.generator.model.type_inspection.visitor.trait import DefaultTypeWalkerTrait
from gendalf.generator.model.type_inspection.visitor.walker import TypeWalker


class ModelASTBuilder:
    def __init__(
        self,
        builder: ModuleASTBuilder,
        factory: ModelFactory,
        trait: t.Optional[TypeWalkerTrait] = None,
    ) -> None:
        self.__builder = builder
        self.__factory = factory
        self.__trait = trait or DefaultTypeWalkerTrait()

        self.__hierarchy = list[type[object]]()
        self.__registry = dict[type[object], TypeRef]()
        self.__analyzer = TypeWalker(
            self.__trait,
            ModelASTGenerator(self.__builder, self.__factory, self.__hierarchy, self.__registry),
        )

    def create_def(
        self,
        name: str,
        fields: t.Mapping[str, type[object]],
        doc: t.Optional[str] = None,
    ) -> ClassRefBuilder:
        with self.__factory.create_class_def(self.__builder, name).docstring(doc) as class_def:
            for field, annotation in fields.items():
                class_def.field_def(field, self.resolve(annotation))

        return class_def.ref()

    def update(self, types: t.Collection[type[object]]) -> None:
        todo = set(types) - self.__registry.keys()

        for type_ in todo:
            context = GenContext(deque([GenContext.Item([])]))
            self.__analyzer.walk(type_, context)

            self.__registry[type_] = context.last.types[0]

    def resolve(self, type_: type[object]) -> TypeRef:
        return self.__registry[type_]

    def assign_expr(
        self,
        source: Expr,
        type_: type[object],
        mode: t.Literal["original", "model"],
        builder: ScopeASTBuilder,
    ) -> Expr:
        context = AssignExprContext(deque([AssignExprContext.Item(builder.attr(source), [])]))

        resolve = TypeInfo.from_type if mode == "original" else self.resolve

        walker = TypeWalker(self.__trait, AssignExprGenerator(builder, resolve))
        walker.walk(type_, context)

        return context.last.exprs[0]


@dataclass()
class GenContext:
    @dataclass()
    class Item:
        types: t.MutableSequence[TypeRef]

    stack: t.MutableSequence[Item]

    @property
    def last(self) -> Item:
        return self.stack[-1]

    def enter(self) -> Item:
        context = self.Item(types=[])
        self.stack.append(context)

        return context

    def leave(self) -> Item:
        return self.stack.pop()


class ModelASTGenerator(TypeVisitorDecorator[GenContext]):
    def __init__(
        self,
        builder: ModuleASTBuilder,
        factory: ModelFactory,
        hierarchy: t.MutableSequence[type[object]],
        registry: t.MutableMapping[type[object], TypeRef],
    ) -> None:
        self.__builder = builder
        self.__factory = factory
        self.__registry = registry
        self.__hierarchy = hierarchy

    @override
    def enter_scalar(self, context: ScalarContext, meta: GenContext) -> None:
        pass

    @override
    def leave_scalar(self, context: ScalarContext, meta: GenContext) -> None:
        self.__add_model(meta, context.type_, TypeInfo.from_type(context.type_))

    @override
    def enter_enum(self, context: EnumContext, meta: GenContext) -> None:
        pass

    @override
    def leave_enum(self, context: EnumContext, meta: GenContext) -> None:
        ref = self.__builder.literal_type(*(val.name for val in context.values))
        self.__add_model(meta, context.type_, ref)

    @override
    def enter_enum_value(self, context: EnumValueContext, meta: GenContext) -> None:
        pass

    @override
    def leave_enum_value(self, context: EnumValueContext, meta: GenContext) -> None:
        pass

    @override
    def enter_container(self, context: ContainerContext, meta: GenContext) -> None:
        meta.enter()

    @override
    def leave_container(self, context: ContainerContext, meta: GenContext) -> None:
        inner = meta.leave()
        ref = self.__builder.generic_type(context.origin, *inner.types)
        self.__add_model(meta, context.type_, ref)

    @override
    def enter_structure(self, context: StructureContext, meta: GenContext) -> None:
        meta.enter()

    @override
    def leave_structure(self, context: StructureContext, meta: GenContext) -> None:
        inner = meta.leave()

        ref = self.__registry.get(context.type_)
        if ref is None:
            with self.__factory.create_class_def(self.__builder, context.name).docstring(
                context.description
            ) as class_def:
                for field, annotation in zip(context.fields, inner.types):
                    class_def.field_def(field.name, annotation)

            ref = class_def

        self.__add_model(meta, context.type_, ref)

    @override
    def enter_structure_field(self, context: StructureFieldContext, meta: GenContext) -> None:
        pass

    @override
    def leave_structure_field(self, context: StructureFieldContext, meta: GenContext) -> None:
        pass

    def __add_model(self, meta: GenContext, type_: type[object], ref: TypeRef) -> None:
        if type_ not in self.__registry:
            self.__registry[type_] = ref
            self.__hierarchy.append(type_)

        meta.last.types.append(ref)


@dataclass()
class AssignExprContext:
    @dataclass()
    class Item:
        source: AttrASTBuilder
        exprs: t.MutableSequence[Expr]

    stack: t.MutableSequence[Item]

    @property
    def last(self) -> Item:
        return self.stack[-1]

    def enter(self, source: AttrASTBuilder) -> Item:
        context = self.Item(source=source, exprs=[])
        self.stack.append(context)

        return context

    def leave(self) -> Item:
        return self.stack.pop()


class AssignExprGenerator(TypeVisitorDecorator[AssignExprContext]):
    def __init__(self, builder: ScopeASTBuilder, resolver: t.Callable[[type[object]], TypeRef]) -> None:
        self.__builder = builder
        self.__resolver = resolver

    @override
    def enter_scalar(self, context: ScalarContext, meta: AssignExprContext) -> None:
        pass

    @override
    def leave_scalar(self, context: ScalarContext, meta: AssignExprContext) -> None:
        meta.last.exprs.append(meta.last.source)

    @override
    def enter_enum(self, context: EnumContext, meta: AssignExprContext) -> None:
        meta.enter(meta.last.source)

    @override
    def leave_enum(self, context: EnumContext, meta: AssignExprContext) -> None:
        scope = meta.leave()
        # TODO: support t.Literal
        meta.last.exprs.append(scope.source.attr("name"))

    @override
    def enter_enum_value(self, context: EnumValueContext, meta: AssignExprContext) -> None:
        pass

    @override
    def leave_enum_value(self, context: EnumValueContext, meta: AssignExprContext) -> None:
        pass

    @override
    def enter_container(self, context: ContainerContext, meta: AssignExprContext) -> None:
        if str(context.type_).startswith("typing.Optional"):
            source = meta.last.source

        elif issubclass(context.origin, t.Mapping):
            source = self.__builder.attr("_".join((*meta.last.source.parts, "value")))

        else:
            source = self.__builder.attr("_".join((*meta.last.source.parts, "item")))

        meta.enter(source)

    @override
    def leave_container(self, context: ContainerContext, meta: AssignExprContext) -> None:
        # TODO: set / list / dict compr
        inner = meta.leave()
        item = inner.exprs[0]

        if context.origin is t.Optional:  # type: ignore[comparison-overlap]
            expr = self.__builder.ternary_not_none_expr(body=item, test=meta.last.source)

        elif issubclass(context.origin, t.Sequence):
            expr = self.__builder.list_expr(items=meta.last.source, target=inner.source, item=item)

        elif issubclass(context.origin, t.Mapping):
            key_var = "_".join((*meta.last.source.parts, "key"))
            expr = self.__builder.dict_expr(
                items=self.__builder.attr(meta.last.source, "items").call(),
                target=self.__builder.tuple_expr(self.__builder.attr(key_var), inner.source),
                key=self.__builder.attr(key_var),
                value=inner.exprs[1],
            )

        elif issubclass(context.origin, t.Collection):
            expr = self.__builder.set_expr(items=meta.last.source, target=inner.source, item=item)

        else:
            raise ValueError(context, meta)

        meta.last.exprs.append(expr)

    @override
    def enter_structure(self, context: StructureContext, meta: AssignExprContext) -> None:
        meta.enter(meta.last.source)

    @override
    def leave_structure(self, context: StructureContext, meta: AssignExprContext) -> None:
        nested = meta.leave()
        meta.last.exprs.append(
            self.__builder.call(
                func=self.__resolver(context.type_),
                kwargs={field.name: expr for field, expr in zip(context.fields, nested.exprs)},
            )
        )

    @override
    def enter_structure_field(self, context: StructureFieldContext, meta: AssignExprContext) -> None:
        meta.enter(self.__builder.attr(meta.last.source, context.name))

    @override
    def leave_structure_field(self, context: StructureFieldContext, meta: AssignExprContext) -> None:
        nested = meta.leave()
        meta.last.exprs.append(nested.exprs[0])
