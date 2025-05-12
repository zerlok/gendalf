from pathlib import Path

import pytest
from astlab.info import TypeInfo

from gendalf.generator.abc import CodeGenerator
from gendalf.generator.fastapi import FastAPICodeGenerator
from gendalf.generator.model import CodeGeneratorContext, CodeGeneratorResult
from gendalf.model import EntrypointInfo, UnaryUnaryMethodInfo


@pytest.mark.parametrize(
    "context",
    [
        pytest.param(
            CodeGeneratorContext(
                entrypoints=[
                    EntrypointInfo(
                        name="Users",
                        doc=None,
                        type_=TypeInfo.from_str("my_service.users:UserManager"),
                        methods=[
                            UnaryUnaryMethodInfo(
                                name="get_user_by_id",
                                doc=None,
                                params=[],
                                returns=...,
                            )
                        ],
                    ),
                ],
                source=Path("test_source"),
                output=Path("test_output"),
                package=None,
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
    return FastAPICodeGenerator()
