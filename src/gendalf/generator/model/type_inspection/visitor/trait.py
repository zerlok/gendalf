import enum
import inspect
import typing as t
import uuid
from dataclasses import MISSING, is_dataclass
from dataclasses import fields as get_dataclass_fields
from datetime import date, datetime, time, timedelta

from gendalf._typing import override
from gendalf.generator.model.type_inspection.visitor.abc import TypeWalkerTrait
from gendalf.generator.model.type_inspection.visitor.model import (
    ContainerContext,
    Context,
    EnumContext,
    EnumValueContext,
    ScalarContext,
    StructureContext,
    StructureFieldContext,
)
from gendalf.option import Option


class DefaultTypeWalkerTrait(TypeWalkerTrait):
    @override
    def extract(self, obj: object) -> t.Optional[Context]:
        for extractor in (
            self.extract_scalar,
            self.extract_enum,
            self.extract_container,
            self.extract_structure,
        ):
            context = extractor(obj)
            if context is not None:
                return context

        details = "unsupported type"
        raise TypeError(details, obj)

    def extract_scalar(self, obj: object) -> t.Optional[ScalarContext]:
        if obj is None or obj is type(None):
            return ScalarContext(type_=type(None))

        if obj is Ellipsis:
            return ScalarContext(type_=type(Ellipsis))

        if isinstance(obj, type) and issubclass(
            obj, (bytes, bytearray, bool, int, float, complex, str, time, date, datetime, timedelta, uuid.UUID)
        ):
            return ScalarContext(type_=obj)

        if obj is t.Any:
            return ScalarContext(type_=object)

        return None

    def extract_enum(self, obj: object) -> t.Optional[EnumContext]:
        if t.get_origin(obj) is t.Literal:
            return EnumContext(
                type_=t.cast("type[object]", obj),
                name=None,
                values=tuple(
                    EnumValueContext(
                        type_=type(value),
                        name=value,
                        value=value,
                    )
                    for value in t.get_args(obj)
                ),
            )

        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            return EnumContext(
                type_=obj,
                name=obj.__name__,
                values=tuple(
                    EnumValueContext(
                        type_=obj,
                        name=el.name,
                        value=el.value,
                    )
                    for el in obj
                ),
                description=get_enum_doc(obj),
            )

        return None

    def extract_container(self, obj: object) -> t.Optional[ContainerContext]:
        if (origin := t.get_origin(obj)) is not None and origin not in {t.Literal, t.Generic}:
            inners = t.get_args(obj)

            # NOTE: `typing.Optional[SomeType]` case: check if `inner` is a pair of some type and none type.
            if origin is t.Union and len(inners) == 2 and inners[1] is type(None):  # noqa: PLR2004
                origin = t.Optional
                inners = inners[:1]

            return ContainerContext(
                type_=t.cast("type[object]", obj),
                origin=origin,
                inners=inners,
            )

        return None

    def extract_structure(self, obj: object) -> t.Optional[StructureContext]:
        if not isinstance(obj, type):
            return None

        if is_dataclass(obj):
            fields = list[StructureFieldContext]()

            for field in get_dataclass_fields(obj):
                # TODO: handle str case (forward ref)
                if isinstance(field.type, str):
                    raise TypeError(field.type, field, obj)

                fields.append(
                    StructureFieldContext(
                        type_=field.type,
                        name=field.name,
                        annotation=field.type,
                        default_value=field.default if field.default is not MISSING else Option[object].empty(),
                    )
                )

            return StructureContext(
                type_=obj,
                name=obj.__name__,
                fields=tuple(fields),
                description=get_dataclass_doc(obj),
            )

        # TODO: support more structured types, e.g. attrs or simple python classes with properties

        return None


def get_enum_doc(type_: type[enum.Enum]) -> t.Optional[str]:
    doc = inspect.getdoc(type_)

    # Python enums provides base enum class documentation if custom docstring is not set in custom enum definition.
    # Don't use it as docstring.
    return doc if doc != inspect.getdoc(enum.Enum) else None


def get_dataclass_doc(dc: type[object]) -> t.Optional[str]:
    doc = inspect.getdoc(dc)
    if doc is None:
        return None

    # skip `self`
    params = list(inspect.signature(dc.__init__).parameters.values())[1:]
    init_signature_doc = f"{dc.__name__}{inspect.Signature(params)}"

    # Python dataclasses provides init constructor signature documentation if custom docstring is not set in class
    # definition. Don't use it as docstring (e.g. don't expose internal implementation to API level).
    return doc if doc != init_signature_doc else None
