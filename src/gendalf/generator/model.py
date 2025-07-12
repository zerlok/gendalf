from __future__ import annotations

import typing as t
from dataclasses import dataclass

if t.TYPE_CHECKING:
    from pathlib import Path

    from gendalf.model import EntrypointInfo


@dataclass(frozen=True)
class CodeGeneratorContext:
    source: Path
    entrypoints: t.Sequence[EntrypointInfo]
    output: Path
    package: t.Optional[str]


@dataclass(frozen=True)
class CodeGeneratorResult:
    @dataclass(frozen=True)
    class File:
        path: Path
        content: str

    files: t.Sequence[File]
