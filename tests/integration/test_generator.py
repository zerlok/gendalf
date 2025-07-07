import typing as t
from pathlib import Path

import pytest
from astlab.types import ModuleLoader, TypeAnnotator, TypeInspector, TypeLoader

from gendalf.entrypoint.inspection import EntrypointInspector
from gendalf.generator.abc import CodeGenerator
from gendalf.generator.fastapi import FastAPICodeGenerator
from gendalf.generator.model import CodeGeneratorContext, CodeGeneratorResult


@pytest.mark.parametrize(
    ("kind", "case_dir", "input_rglob", "output_rglob"),
    [
        pytest.param(
            "fastapi",
            Path.cwd() / "examples" / "my_greeter",
            "src/**/*.py",
            "generated/**/*.py",
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
def code_generator(
    kind: str,
    type_loader: TypeLoader,
    type_inspector: TypeInspector,
    type_annotator: TypeAnnotator,
) -> CodeGenerator:
    if kind == "fastapi":
        return FastAPICodeGenerator(type_loader, type_inspector, type_annotator)

    else:
        msg = "unknown code generator kind"
        raise ValueError(msg, kind)


@pytest.fixture
def module_loader(source_dir: Path) -> t.Iterator[ModuleLoader]:
    assert source_dir.exists()

    with ModuleLoader.with_sys_path(source_dir) as loader:
        yield loader


@pytest.fixture
def type_loader(module_loader: ModuleLoader) -> TypeLoader:
    return TypeLoader(module_loader)


@pytest.fixture
def type_inspector() -> TypeInspector:
    return TypeInspector()


@pytest.fixture
def type_annotator(module_loader: ModuleLoader) -> TypeAnnotator:
    return TypeAnnotator(module_loader)


@pytest.fixture
def entrypoint_inspector(module_loader: ModuleLoader, type_inspector: TypeInspector) -> EntrypointInspector:
    return EntrypointInspector(module_loader, type_inspector)


@pytest.fixture
def source_dir(case_dir: Path) -> Path:
    return case_dir / "src"


@pytest.fixture
def input_rglob() -> t.Optional[str]:
    return None


@pytest.fixture
def input_paths(case_dir: Path, input_rglob: t.Optional[str]) -> t.Sequence[Path]:
    return list(case_dir.rglob(input_rglob if input_rglob is not None else "src/**/*.py"))


@pytest.fixture
def code_generator_context(
    source_dir: Path,
    input_paths: t.Sequence[Path],
    output_dir: Path,
    entrypoint_inspector: EntrypointInspector,
) -> CodeGeneratorContext:
    return CodeGeneratorContext(
        source=source_dir,
        entrypoints=list(entrypoint_inspector.inspect_paths(input_paths)),
        output=output_dir,
        package=None,
    )


@pytest.fixture
def output_dir(case_dir: Path) -> Path:
    return case_dir / "generated"


@pytest.fixture
def output_rglob() -> t.Optional[str]:
    return None


@pytest.fixture
def output_paths(case_dir: Path, output_rglob: t.Optional[str]) -> t.Sequence[Path]:
    return list(case_dir.rglob(output_rglob if output_rglob is not None else "generated/**/*.py"))


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
