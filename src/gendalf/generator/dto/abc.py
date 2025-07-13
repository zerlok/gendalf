import abc
import typing as t

from astlab.abc import Expr, TypeRef
from astlab.builder import ClassTypeRefBuilder, ScopeASTBuilder
from astlab.types import TypeInfo


class DtoMapper(metaclass=abc.ABCMeta):
    """
    Build DTO class definitions, encode, decode and DTO & domain mapping expressions.

    * DTO decoding (deserialize / parse raw data to DTO)
    * DTO → Domain (aka inbound mapping, build domain object from DTO)
    * Domain → DTO (aka outbound mapping, build DTO from domain object)
    * DTO encoding (serialize / dump DTO to raw format)
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
        """
        Create DTO class in the given scope using domain class info OR using provided name and domain fields.

        :scope: keeps the generated code
        :info: domain type info (mapper should automatically detect public fields and make DTO mapping for them)
        :name: name of the DTO class
        :fields: fields for DTO class with corresponding names and domain type infos (manually specify a set of fields)
        """
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

    # TODO: consider statements interface
    @abc.abstractmethod
    def build_dto_to_domain_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: Expr) -> Expr:
        """
        Build mapping expression from the DTO type to domain type in the given scope.

        :scope: keeps generated code
        :domain: an info about the domain type that has a corresponding DTO class
        :source: an expression of DTO object the mapping should be built from
        """
        raise NotImplementedError

    @abc.abstractmethod
    def build_domain_to_dto_expr(self, scope: ScopeASTBuilder, domain: TypeInfo, source: Expr) -> Expr:
        """
        Build mapping expression from the domain type to DTO type in the given scope.

        :scope: keeps generated code
        :domain: an info about the domain type that has a corresponding DTO class
        :source: an expression of domain object the mapping should be built from
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
