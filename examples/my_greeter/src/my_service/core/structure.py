import typing as t

from gendalf.entrypoint.decorator import entrypoint
from my_service.core.greeter.model import ComplexStructure, UserInfo


@entrypoint(name="Structure")
class StructureController:
    async def complex(self) -> t.Sequence[ComplexStructure]:
        return [
            ComplexStructure(
                items={
                    key: ComplexStructure.Item(
                        users=[
                            UserInfo(
                                id_=i * 3 + j,
                                name=f"name-{i:03}-{j:03}",
                            )
                            for j in range(3)
                        ]
                    )
                    for key in ("group", "part")
                }
            )
            for i in range(3)
        ]
