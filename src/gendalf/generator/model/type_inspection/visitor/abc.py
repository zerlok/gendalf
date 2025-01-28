import abc
import typing as t

from gendalf.generator.model.type_inspection.visitor.model import (
    ContainerContext,
    Context,
    EnumContext,
    EnumValueContext,
    ScalarContext,
    StructureContext,
    StructureFieldContext,
)

T_contra = t.TypeVar("T_contra", contravariant=True)


class TypeVisitor(t.Generic[T_contra], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def visit_scalar(self, context: ScalarContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def visit_enum(self, context: EnumContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def visit_enum_value(self, context: EnumValueContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def visit_container(self, context: ContainerContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def visit_structure(self, context: StructureContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def visit_structure_field(self, context: StructureFieldContext, meta: T_contra) -> None:
        raise NotImplementedError


class TypeVisitorDecorator(t.Generic[T_contra], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def enter_scalar(self, context: ScalarContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def leave_scalar(self, context: ScalarContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def enter_enum(self, context: EnumContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def leave_enum(self, context: EnumContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def enter_enum_value(self, context: EnumValueContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def leave_enum_value(self, context: EnumValueContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def enter_container(self, context: ContainerContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def leave_container(self, context: ContainerContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def enter_structure(self, context: StructureContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def leave_structure(self, context: StructureContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def enter_structure_field(self, context: StructureFieldContext, meta: T_contra) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def leave_structure_field(self, context: StructureFieldContext, meta: T_contra) -> None:
        raise NotImplementedError


class TypeWalkerTrait(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def extract(self, obj: object) -> t.Optional[Context]:
        raise NotImplementedError
