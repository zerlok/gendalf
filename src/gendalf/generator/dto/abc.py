import abc
import typing as t

from astlab.abc import Expr, TypeRef
from astlab.builder import ClassBodyASTBuilder, ClassHeaderASTBuilder, ScopeASTBuilder


class DtoMapperTrait(metaclass=abc.ABCMeta):
    """Interface for :class:`DtoMapper` to customize DTO definition and serialization strategy."""

    @abc.abstractmethod
    def create_dto_class_def(self, scope: ScopeASTBuilder, name: str) -> ClassHeaderASTBuilder:
        """Create DTO class header definition in the given scope."""
        raise NotImplementedError

    @abc.abstractmethod
    def add_dto_field_def(
        self,
        scope: ClassBodyASTBuilder,
        name: str,
        info: TypeRef,
        default: t.Optional[Expr] = None,
    ) -> None:
        """Add field to a given DTO class definition."""
        raise NotImplementedError

    @abc.abstractmethod
    def build_dto_decode_expr(self, scope: ScopeASTBuilder, dto: TypeRef, source: Expr) -> Expr:
        """
        Build DTO decode expression in the given scope.

        :scope: keeps generated code
        :dto: a reference to DTO class definition
        :source: a DTO object should be decoded from
        """
        raise NotImplementedError

    @abc.abstractmethod
    def build_dto_encode_expr(self, scope: ScopeASTBuilder, dto: TypeRef, source: Expr) -> Expr:
        """
        Build DTO encode expression in the given scope.

        :scope: keeps generated code
        :dto: a reference to DTO class definition
        :source: a DTO object that should be encoded
        """
        raise NotImplementedError
