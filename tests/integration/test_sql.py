import typing as t
from pathlib import Path

import pytest
from astlab.types import ModuleLoader, TypeAnnotator, TypeInspector, TypeLoader

from gendalf.generator.abc import SQLCodeGenerator
from gendalf.generator.model import CodeGeneratorResult, SQLCodeGeneratorContext
from gendalf.generator.sqlcast import SQLCastCodeGenerator
from gendalf.sql.inspector import SQLInspector


@pytest.mark.parametrize(
    ("case_dir", "input_rglob"),
    [
        pytest.param(Path.cwd() / "examples" / "my_greeter", "src/**/*.sql", id="examples my_greeter"),
    ],
)
def test_code_generator_returns_expected_result(
    code_generator: SQLCodeGenerator,
    sql_generator_context: SQLCodeGeneratorContext,
    expected_sql_generator_result: CodeGeneratorResult,
) -> None:
    assert sort_files(code_generator.generate(sql_generator_context)) == expected_sql_generator_result


@pytest.fixture
def code_generator() -> SQLCodeGenerator:
    return SQLCastCodeGenerator()


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
def sql_inspector() -> SQLInspector:
    return SQLInspector(dialect="postgres")


@pytest.fixture
def source_dir(case_dir: Path) -> Path:
    return case_dir / "src"


@pytest.fixture
def input_rglob() -> t.Optional[str]:
    return None


@pytest.fixture
def input_paths(case_dir: Path, input_rglob: t.Optional[str]) -> t.Sequence[Path]:
    assert case_dir.is_dir()
    return list(case_dir.rglob(input_rglob if input_rglob is not None else "src/**/*.sql"))


@pytest.fixture
def sql_generator_context(
    input_paths: t.Sequence[Path],
    output_dir: Path,
    sql_inspector: SQLInspector,
) -> SQLCodeGeneratorContext:
    return SQLCodeGeneratorContext(
        sqls=list(sql_inspector.inspect_paths(input_paths)),
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
def expected_output_paths(
    output_dir: Path,
    output_rglob: t.Optional[str],
) -> t.Sequence[Path]:
    paths = [output_dir / "db" / "__init__.py"]
    paths.extend((output_dir / "db").rglob(output_rglob if output_rglob is not None else "*.py"))

    return paths


@pytest.fixture
def expected_sql_generator_result(expected_output_paths: t.Sequence[Path]) -> CodeGeneratorResult:
    return sort_files(
        CodeGeneratorResult(
            files=[
                CodeGeneratorResult.File(
                    path=path,
                    content=path.read_text(),
                )
                for path in expected_output_paths
            ],
        ),
    )


def sort_files(result: CodeGeneratorResult) -> CodeGeneratorResult:
    return CodeGeneratorResult(files=sorted(result.files, key=_get_file_key))


def _get_file_key(file: CodeGeneratorResult.File) -> Path:
    return file.path
