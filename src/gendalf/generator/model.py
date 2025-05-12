from __future__ import annotations

import typing as t
from dataclasses import dataclass
from pathlib import Path

from gendalf.model import EntrypointInfo


@dataclass(frozen=True)
class CodeGeneratorContext:
    entrypoints: t.Sequence[EntrypointInfo]
    source: Path
    output: Path
    package: t.Optional[str]


@dataclass(frozen=True)
class CodeGeneratorResult:
    @dataclass(frozen=True)
    class File:
        path: Path
        content: str

    files: t.Sequence[File]
