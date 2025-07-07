import abc
import typing as t

from astlab.abc import Expr, TypeRef
from astlab.builder import ClassTypeRefBuilder, ScopeASTBuilder
from astlab.types import TypeInfo


class DtoMapper(metaclass=abc.ABCMeta):
    """
    Build DTO class definitions, encode, decode and DTO & domain mapping expressions.

    * DTO decoding (deserialize / parse raw data to DTO)
    * Transport → Domain (aka inbound mapping, build domain object from DTO)
    * Domain → Transport (aka outbound mapping, build DTO from domain object)
    * DTO encode (serialize / dump DTO to raw format)
    """

    @abc.abstractmethod
    @t.overload
    def create_dto_def(
        self,
        *,
        scope: ScopeASTBuilder,
        info: TypeInfo,
    ) -> TypeRef: ...

    @abc.abstractmethod
    @t.overload
    def create_dto_def(
        self,
        *,
        scope: ScopeASTBuilder,
        name: str,
        fields: t.Mapping[str, TypeInfo],
        doc: t.Optional[str] = None,
    ) -> ClassTypeRefBuilder: ...

    @abc.abstractmethod
    def create_dto_def(
        self,
        *,
        scope: ScopeASTBuilder,
        info: t.Optional[TypeInfo] = None,
        name: t.Optional[str] = None,
        fields: t.Optional[t.Mapping[str, TypeInfo]] = None,
        doc: t.Optional[str] = None,
    ) -> TypeRef:
        """Create DTO class in the given scope using provided domain class info or the given name and domain fields."""
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
