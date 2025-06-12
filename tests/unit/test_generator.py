from pathlib import Path

import pytest
from astlab.types import NamedTypeInfo, TypeInspector

from gendalf.generator.abc import CodeGenerator
from gendalf.generator.fastapi import FastAPICodeGenerator
from gendalf.generator.model import CodeGeneratorContext, CodeGeneratorResult
from gendalf.model import EntrypointInfo, ParameterInfo, UnaryUnaryMethodInfo

_INSPECTOR = TypeInspector()


@pytest.mark.parametrize(
    ("context", "expected_result"),
    [
        pytest.param(
            CodeGeneratorContext(
                source=Path.cwd() / "examples" / "my_greeter" / "src",
                entrypoints=[
                    EntrypointInfo(
                        name="UserManager",
                        doc=None,
                        type_=NamedTypeInfo.build("my_service.users", "UserManager"),
                        methods=[
                            UnaryUnaryMethodInfo(
                                name="get_user_by_id",
                                doc=None,
                                params=[ParameterInfo("id", _INSPECTOR.inspect(int))],
                                returns=NamedTypeInfo.build("my_service.users", "User"),
                            )
                        ],
                    ),
                ],
                output=Path("gen_output"),
                package=None,
            ),
            CodeGeneratorResult(
                files=[
                    # TODO: prepare valid code for content
                    CodeGeneratorResult.File(
                        path=Path("gen_output") / "api" / "model.py",
                        content="",
                    ),
                    CodeGeneratorResult.File(
                        path=Path("gen_output") / "api" / "server.py",
                        content="",
                    ),
                    CodeGeneratorResult.File(
                        path=Path("gen_output") / "api" / "client.py",
                        content="",
                    ),
                ],
            ),
        ),
    ],
)
def test_code_generator_returns_expected_result(
    gen: CodeGenerator,
    context: CodeGeneratorContext,
    expected_result: CodeGeneratorResult,
) -> None:
    assert gen.generate(context) == expected_result


@pytest.fixture
def gen() -> FastAPICodeGenerator:
    return FastAPICodeGenerator(TypeInspector())
