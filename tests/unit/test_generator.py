import typing as t
from pathlib import Path

import pytest
from astlab.reader import walk_package_modules
from astlab.types import ModuleLoader, TypeInspector, TypeLoader

from gendalf.entrypoint.inspection import EntrypointInspector
from gendalf.generator.abc import CodeGenerator
from gendalf.generator.fastapi import FastAPICodeGenerator
from gendalf.generator.model import CodeGeneratorContext, CodeGeneratorResult

_INSPECTOR = TypeInspector()


@pytest.mark.parametrize(
    ("source", "output"),
    [
        pytest.param(
            Path.cwd() / "examples" / "my_greeter" / "src",
            Path.cwd() / "examples" / "my_greeter" / "generated",
        ),
    ],
)
def test_code_generator_returns_expected_result(
    gen: CodeGenerator,
    code_gen_context: CodeGeneratorContext,
    code_gen_result: CodeGeneratorResult,
) -> None:
    assert gen.generate(code_gen_context) == code_gen_result


@pytest.fixture
def gen(type_inspector: TypeInspector, type_loader: TypeLoader) -> FastAPICodeGenerator:
    return FastAPICodeGenerator(TypeInspector(), type_loader)


@pytest.fixture
def type_inspector() -> TypeInspector:
    return TypeInspector()


@pytest.fixture
def type_loader(module_loader: ModuleLoader) -> TypeLoader:
    return TypeLoader(module_loader)


@pytest.fixture
def module_loader(source: Path) -> t.Iterator[ModuleLoader]:
    with ModuleLoader.with_sys_path(source) as loader:
        yield loader


@pytest.fixture
def entrypoint_inspector(module_loader: ModuleLoader, type_inspector: TypeInspector) -> EntrypointInspector:
    return EntrypointInspector(module_loader, type_inspector)


@pytest.fixture
def code_gen_context(source: Path, output: Path, entrypoint_inspector: EntrypointInspector) -> CodeGeneratorContext:
    assert source.exists()

    return CodeGeneratorContext(
        source=source,
        entrypoints=list(entrypoint_inspector.inspect_dir(source)),
        output=output,
        package=None,
    )


@pytest.fixture
def code_gen_result(output: Path) -> CodeGeneratorResult:
    return CodeGeneratorResult(
        files=[
            CodeGeneratorResult.File(
                path=path,
                content=path.read_text(),
            )
            for path in walk_package_modules(output)
        ],
    )
