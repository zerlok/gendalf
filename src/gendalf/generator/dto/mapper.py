from __future__ import annotations

import typing as t
from collections import deque
from dataclasses import dataclass

from astlab.abc import Expr, TypeRef
from astlab.builder import AttrASTBuilder, ClassRefBuilder, ScopeASTBuilder
from astlab.types import TypeInfo

from gendalf._typing import override
from gendalf.generator.dto.abc import DtoMapperTrait


class DtoMapper:
    """
    Build DTO class definitions, encode, decode and DTO & domain mapping expressions.

    * DTO decoding (deserialize / parse raw data to DTO)
    * Transport → Domain (aka inbound mapping, build domain object from DTO)
    * Domain → Transport (aka outbound mapping, build DTO from domain object)
    * DTO encode (serialize / dump DTO to raw format)
    """

    def __init__(self, trait: DtoMapperTrait) -> None:
        self.__trait = trait

        self.__domain_to_dto = dict[TypeInfo, TypeRef]()
        self.__dto_order = list[TypeInfo]()
        self.__class_def_generator = DtoClassDefGenerator(self.__trait)
        self.__assign_expr_generator = DtoAssignExprGenerator()

    def create_dto_class_def(
        self,
        scope: ScopeASTBuilder,
        name: str,
        fields: t.Mapping[str, TypeInfo],
        doc: t.Optional[str] = None,
    ) -> ClassRefBuilder:
        """
        Build transport model class definition.

        Uses domain fields' :class:`TypeInfo` to duplicate them on transport and use them in DTO accordingly.

        Only struct & literal types are copied to transport level, builtin scalar & container types (e.g. int, str,
        list) are reused.
        """

        for info in set(fields.values()) - self.__domain_to_dto.keys():
            report = self.__analyzer.analyze(info)
            self.__domain_to_dto.update()
            self.__registry[type_] = context.last.types[0]

        with self.__trait.create_dto_class_def(scope, name).docstring(doc) as dto_class_def:
            for field, annotation in fields.items():
                dto_field_annotation = self.__domain_to_dto[annotation]
                self.__trait.add_dto_field_def(dto_class_def, field, dto_field_annotation)

        self.__dto_order.append(dto_class_def)

        return dto_class_def.ref()

    def build_dto_decode_expr(self, scope: ScopeASTBuilder, dto: TypeRef, source: Expr) -> Expr:
        return self.__trait.build_dto_decode_expr(scope, dto, source)

    def build_dto_to_domain_expr(self, scope: ScopeASTBuilder, dto: TypeRef, domain: TypeRef, source: Expr) -> Expr:
        context = AssignExprContext(deque([AssignExprContext.Item(scope.attr(source), [])]))

        resolve = TypeInfo.from_type if mode == "original" else self.resolve

        inspector = TypeKindInspector(DtoAssignExprGenerator(scope, resolve))
        inspector.inspect(type_, context)

        return context.last.exprs[0]

    def build_domain_to_dto_expr(self, scope: ScopeASTBuilder, domain: TypeRef, dto: TypeRef, source: Expr) -> Expr:
        context = AssignExprContext(deque([AssignExprContext.Item(scope.attr(source), [])]))

        resolve = TypeInfo.from_type if mode == "original" else self.resolve

        inspector = TypeKindInspector(DtoAssignExprGenerator(scope, resolve))
        inspector.inspect(type_, context)

        return context.last.exprs[0]

    def build_dto_encode_expr(self, scope: ScopeASTBuilder, dto: TypeRef, source: Expr) -> Expr:
        return self.__trait.build_dto_encode_expr(scope, dto, source)


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


class DtoClassDefGenerator:
    def __init__(
        self,
        trait: DtoMapperTrait,
        hierarchy: t.MutableSequence[TypeInfo],
        registry: t.MutableMapping[TypeInfo, TypeRef],
    ) -> None:
        self.__trait = trait
        self.__registry = registry
        self.__hierarchy = hierarchy

    def generate(self):
        pass

    @override
    def enter_scalar(self, kind: ScalarTypeKind, meta: GenContext) -> None:
        pass

    @override
    def leave_scalar(self, kind: ScalarTypeKind, meta: GenContext) -> None:
        self.__add_model(meta, kind.info, kind.info)

    @override
    def enter_enum(self, kind: EnumTypeKind, meta: GenContext) -> None:
        pass

    @override
    def leave_enum(self, kind: EnumTypeKind, meta: GenContext) -> None:
        ref = self.__builder.literal_type(*(val.name for val in kind.values))
        self.__add_model(meta, kind.info, ref)

    @override
    def enter_enum_value(self, kind: EnumValueTypeKind, meta: GenContext) -> None:
        pass

    @override
    def leave_enum_value(self, kind: EnumValueTypeKind, meta: GenContext) -> None:
        pass

    @override
    def enter_container(self, kind: ContainerTypeKind, meta: GenContext) -> None:
        meta.enter()

    @override
    def leave_container(self, kind: ContainerTypeKind, meta: GenContext) -> None:
        inner = meta.leave()
        ref = self.__builder.generic_type(kind.origin, *inner.types)
        self.__add_model(meta, kind.info, ref)

    @override
    def enter_structure(self, kind: StructureTypeKind, meta: GenContext) -> None:
        meta.enter()

    @override
    def leave_structure(self, kind: StructureTypeKind, meta: GenContext) -> None:
        inner = meta.leave()

        ref = self.__registry.get(kind.info)
        if ref is None:
            with self.__factory.create_dto_class_def(self.__builder, kind.name).docstring(
                kind.description
            ) as class_def:
                for field, annotation in zip(kind.fields, inner.types):
                    class_def.field_def(field.name, annotation)

            ref = class_def

        self.__add_model(meta, kind.info, ref)

    @override
    def enter_structure_field(self, kind: StructureFieldTypeKind, meta: GenContext) -> None:
        pass

    @override
    def leave_structure_field(self, kind: StructureFieldTypeKind, meta: GenContext) -> None:
        pass

    def __add_model(self, meta: GenContext, type_: TypeInfo, ref: TypeRef) -> None:
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


class DtoAssignExprGenerator(TypeKindVisitorDecorator[AssignExprContext]):
    def __init__(self, resolver: t.Callable[[TypeInfo], TypeRef]) -> None:
        self.__resolver = resolver

    @override
    def enter_scalar(self, kind: ScalarTypeKind, meta: AssignExprContext) -> None:
        pass

    @override
    def leave_scalar(self, kind: ScalarTypeKind, meta: AssignExprContext) -> None:
        meta.last.exprs.append(meta.last.source)

    @override
    def enter_enum(self, kind: EnumTypeKind, meta: AssignExprContext) -> None:
        meta.enter(meta.last.source)

    @override
    def leave_enum(self, kind: EnumTypeKind, meta: AssignExprContext) -> None:
        scope = meta.leave()
        # TODO: support t.Literal
        meta.last.exprs.append(scope.source.attr("name"))

    @override
    def enter_enum_value(self, kind: EnumValueTypeKind, meta: AssignExprContext) -> None:
        pass

    @override
    def leave_enum_value(self, kind: EnumValueTypeKind, meta: AssignExprContext) -> None:
        pass

    @override
    def enter_container(self, kind: ContainerTypeKind, meta: AssignExprContext) -> None:
        if kind.info.name == "typing.Optional":
            source = meta.last.source

        elif issubclass(kind.origin.load(), t.Mapping):
            source = self.__builder.attr("_".join((*meta.last.source.parts, "value")))

        else:
            source = self.__builder.attr("_".join((*meta.last.source.parts, "item")))

        meta.enter(source)

    @override
    def leave_container(self, kind: ContainerTypeKind, meta: AssignExprContext) -> None:
        # TODO: set / list / dict compr
        inner = meta.leave()
        item = inner.exprs[0]

        if kind.origin is t.Optional:  # type: ignore[comparison-overlap]
            expr = self.__builder.ternary_not_none_expr(body=item, test=meta.last.source)

        elif issubclass(kind.origin.load(), t.Sequence):
            expr = self.__builder.list_expr(items=meta.last.source, target=inner.source, item=item)

        elif issubclass(kind.origin.load(), t.Mapping):
            key_var = "_".join((*meta.last.source.parts, "key"))
            expr = self.__builder.dict_expr(
                items=self.__builder.attr(meta.last.source, "items").call(),
                target=self.__builder.tuple_expr(self.__builder.attr(key_var), inner.source),
                key=self.__builder.attr(key_var),
                value=inner.exprs[1],
            )

        elif issubclass(kind.origin.load(), t.Collection):
            expr = self.__builder.set_expr(items=meta.last.source, target=inner.source, item=item)

        else:
            raise ValueError(kind, meta)

        meta.last.exprs.append(expr)

    @override
    def enter_structure(self, kind: StructureTypeKind, meta: AssignExprContext) -> None:
        meta.enter(meta.last.source)

    @override
    def leave_structure(self, kind: StructureTypeKind, meta: AssignExprContext) -> None:
        nested = meta.leave()
        meta.last.exprs.append(
            self.__builder.call(
                func=self.__resolver(kind.info),
                kwargs={field.name: expr for field, expr in zip(kind.fields, nested.exprs)},
            )
        )

    @override
    def enter_structure_field(self, kind: StructureFieldTypeKind, meta: AssignExprContext) -> None:
        meta.enter(self.__builder.attr(meta.last.source, kind.name))

    @override
    def leave_structure_field(self, kind: StructureFieldTypeKind, meta: AssignExprContext) -> None:
        nested = meta.leave()
        meta.last.exprs.append(nested.exprs[0])
