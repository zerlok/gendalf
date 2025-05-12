import sys
from functools import cached_property

from astlab.builder import ClassHeaderASTBuilder, ModuleASTBuilder
from astlab.info import ModuleInfo, TypeInfo

from gendalf._typing import override
from gendalf.generator.transport_model.abc import TMFactory


class DataclassTMFactory(TMFactory):
    @override
    def create_class_def(self, builder: ModuleASTBuilder, name: str) -> ClassHeaderASTBuilder:
        return builder.class_def(name).dataclass(
            frozen=True,
            kw_only=self.__is_kw_only_supported,
        )

    @cached_property
    def __is_kw_only_supported(self) -> bool:
        return sys.version_info >= (3, 10)


class PydanticTMFactory(TMFactory):
    @override
    def create_class_def(self, builder: ModuleASTBuilder, name: str) -> ClassHeaderASTBuilder:
        return builder.class_def(name).inherits(self.__base_model)

    @cached_property
    def __base_model(self) -> TypeInfo:
        return TypeInfo("BaseModel", ModuleInfo(None, "pydantic"))
