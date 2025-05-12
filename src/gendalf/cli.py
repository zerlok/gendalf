import typing as t
from dataclasses import dataclass
from pathlib import Path

import click

from gendalf._typing import assert_never
from gendalf.entrypoint.inspection import inspect_source_dir
from gendalf.entrypoint.printer import Printer
from gendalf.generator.fastapi import FastAPICodeGenerator
from gendalf.generator.model import CodeGeneratorContext


@dataclass(frozen=True)
class CLIContext:
    source: Path
    ignore_module_on_import_error: bool


pass_cli_context = click.make_pass_decorator(CLIContext)


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
        source=source,
        ignore_module_on_import_error=ignore_module_on_import_error,
    )


OPT_OUTPUT = click.option(
    "-o",
    "--output",
    type=click.Path(writable=True, resolve_path=True, path_type=Path),
    default=None,
)


GenKind = t.Literal["fastapi"]


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
    type=str,
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
    package: t.Optional[str],
    dry_run: bool,
) -> None:
    """Generate code for specified python package."""

    gen_context = CodeGeneratorContext(
        entrypoints=list(
            inspect_source_dir(context.source, ignore_module_on_import_error=context.ignore_module_on_import_error)
        ),
        source=context.source,
        output=output if output is not None else context.source,
        package=package,
    )

    if kind == "fastapi":
        gen = FastAPICodeGenerator()
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
    """Show info about the package"""

    printer = Printer(click.echo)

    for entrypoint in inspect_source_dir(
        context.source,
        ignore_module_on_import_error=context.ignore_module_on_import_error,
    ):
        entrypoint.accept(printer)


if __name__ == "__main__":
    cli()
