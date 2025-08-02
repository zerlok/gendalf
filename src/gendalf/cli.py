import typing as t
from functools import cached_property
from pathlib import Path

import click
from astlab.types import ModuleLoader, PackageInfo, TypeAnnotator, TypeInspector, TypeLoader

from gendalf._typing import assert_never
from gendalf.entrypoint.inspection import EntrypointInspector
from gendalf.entrypoint.printer import Printer
from gendalf.generator.aiohttp import AiohttpCodeGenerator
from gendalf.generator.fastapi import FastAPICodeGenerator
from gendalf.generator.model import CodeGeneratorContext
from gendalf.model import EntrypointInfo

if t.TYPE_CHECKING:
    from gendalf.generator.abc import CodeGenerator

T = t.TypeVar("T")


class CLIContext:
    def __init__(
        self,
        base: click.Context,
        source: Path,
        ignore_module_on_import_error: bool,
    ) -> None:
        self.base = base
        self.source: t.Final[Path] = source
        self.ignore_module_on_import_error: t.Final[bool] = ignore_module_on_import_error

    @cached_property
    def module_loader(self) -> ModuleLoader:
        return self.with_resource(ModuleLoader.with_sys_path(self.source))

    @cached_property
    def type_loader(self) -> TypeLoader:
        return TypeLoader(self.module_loader)

    @cached_property
    def type_inspector(self) -> TypeInspector:
        return TypeInspector()

    @cached_property
    def type_annotator(self) -> TypeAnnotator:
        return TypeAnnotator(self.module_loader)

    @cached_property
    def entrypoint_inspector(self) -> EntrypointInspector:
        return EntrypointInspector(self.module_loader, self.type_inspector)

    def inspect_source(self) -> t.Iterable[EntrypointInfo]:
        return self.entrypoint_inspector.inspect_source(
            source=self.source,
            ignore_module_on_import_error=self.ignore_module_on_import_error,
        )

    def with_resource(self, cm: t.ContextManager[T]) -> T:
        return self.base.with_resource(cm)


@click.group()
@click.pass_context
@click.argument(
    "source",
    type=click.Path(exists=True, resolve_path=True, path_type=Path),
)
@click.option(
    "--ignore-module-on-import-error",
    type=bool,
    is_flag=True,
    default=False,
)
def cli(
    context: click.Context,
    source: Path,
    ignore_module_on_import_error: bool,
) -> None:
    context.obj = CLIContext(
        base=context,
        source=source,
        ignore_module_on_import_error=ignore_module_on_import_error,
    )


OPT_OUTPUT = click.option(
    "-o",
    "--output",
    type=click.Path(writable=True, resolve_path=True, path_type=Path),
    default=None,
)


GenKind = t.Literal["fastapi", "aiohttp"]


@cli.command()
@click.pass_obj
@click.argument(
    "kind",
    type=click.Choice(t.get_args(GenKind)),
)
@OPT_OUTPUT
@click.option(
    "-p",
    "--package",
    type=PackageInfo.from_str,
    default=None,
)
@click.option(
    "--dry-run",
    type=bool,
    is_flag=True,
    default=False,
)
def cast(
    context: CLIContext,
    kind: GenKind,
    output: t.Optional[Path],
    package: t.Optional[PackageInfo],
    dry_run: bool,
) -> None:
    """Generate code for specified python package."""

    gen_context = CodeGeneratorContext(
        entrypoints=list(context.inspect_source()),
        output=output if output is not None else context.source,
        package=package,
    )

    gen: CodeGenerator
    if kind == "fastapi":
        gen = FastAPICodeGenerator(
            loader=context.type_loader,
            inspector=context.type_inspector,
            annotator=context.type_annotator,
        )

    elif kind == "aiohttp":
        gen = AiohttpCodeGenerator(
            loader=context.type_loader,
            inspector=context.type_inspector,
            annotator=context.type_annotator,
        )

    else:
        assert_never(kind)

    for file in gen.generate(gen_context).files:
        if dry_run:
            continue

        file.path.parent.mkdir(parents=True, exist_ok=True)
        with file.path.open("w") as fd:
            fd.write(file.content)


@cli.command()
@click.pass_obj
def show(context: CLIContext) -> None:
    """Show info about the package."""

    printer = Printer(
        dest=click.get_text_stream("stdout"),
        annotator=context.type_annotator,
    )

    for entrypoint in context.inspect_source():
        entrypoint.accept(printer)


if __name__ == "__main__":
    cli()
