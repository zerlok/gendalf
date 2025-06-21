import typing as t
from pathlib import Path

import pytest
from astlab.types import ModuleLoader, TypeInspector, TypeLoader

from gendalf.entrypoint.inspection import EntrypointInspector
from gendalf.generator.abc import CodeGenerator
from gendalf.generator.fastapi import FastAPICodeGenerator
from gendalf.generator.model import CodeGeneratorContext, CodeGeneratorResult


@pytest.mark.parametrize(
    ("kind", "source", "input_rglob", "output_dir"),
    [
        pytest.param(
            "fastapi",
            Path().cwd() / "examples" / "my_greeter" / "src",
            "my_service/core/greeter/**/*.py",
            Path.cwd() / "examples" / "my_greeter" / "src" / "my_service" / "api",
        ),
    ],
)
def test_code_generator_returns_expected_result(
    code_generator: CodeGenerator,
    code_generator_context: CodeGeneratorContext,
    code_generator_result: CodeGeneratorResult,
) -> None:
    assert sort_files(code_generator.generate(code_generator_context)) == code_generator_result


@pytest.fixture
def code_generator(kind: str, type_inspector: TypeInspector, type_loader: TypeLoader) -> CodeGenerator:
    if kind == "fastapi":
        return FastAPICodeGenerator(type_inspector, type_loader)

    else:
        msg = "unknown code generator kind"
        raise ValueError(msg, kind)


@pytest.fixture
def type_inspector() -> TypeInspector:
    return TypeInspector()


@pytest.fixture
def type_loader(module_loader: ModuleLoader) -> TypeLoader:
    return TypeLoader(module_loader)


@pytest.fixture
def module_loader(source: Path) -> t.Iterator[ModuleLoader]:
    assert source.exists()

    with ModuleLoader.with_sys_path(source) as loader:
        yield loader


@pytest.fixture
def entrypoint_inspector(module_loader: ModuleLoader, type_inspector: TypeInspector) -> EntrypointInspector:
    return EntrypointInspector(module_loader, type_inspector)


@pytest.fixture
def input_rglob() -> t.Optional[str]:
    return None


@pytest.fixture
def input_paths(source: Path, input_rglob: t.Optional[str]) -> t.Sequence[Path]:
    return list(source.rglob(input_rglob if input_rglob is not None else "*.py"))


@pytest.fixture
def code_generator_context(
    source: Path,
    input_paths: t.Sequence[Path],
    output_dir: Path,
    entrypoint_inspector: EntrypointInspector,
) -> CodeGeneratorContext:
    return CodeGeneratorContext(
        source=source,
        entrypoints=list(entrypoint_inspector.inspect_paths(input_paths)),
        output=output_dir,
        package=None,
    )


@pytest.fixture
def output_rglob() -> t.Optional[str]:
    return None


@pytest.fixture
def output_paths(output_dir: Path, output_rglob: t.Optional[str]) -> t.Sequence[Path]:
    return list(output_dir.rglob(output_rglob if output_rglob is not None else "*.py"))


@pytest.fixture
def code_generator_result(output_paths: t.Sequence[Path]) -> CodeGeneratorResult:
    return sort_files(
        CodeGeneratorResult(
            files=[
                CodeGeneratorResult.File(
                    path=path,
                    content=path.read_text(),
                )
                for path in output_paths
            ],
        )
    )


def sort_files(result: CodeGeneratorResult) -> CodeGeneratorResult:
    return CodeGeneratorResult(files=sorted(result.files, key=_get_file_key))


def _get_file_key(file: CodeGeneratorResult.File) -> Path:
    return file.path
