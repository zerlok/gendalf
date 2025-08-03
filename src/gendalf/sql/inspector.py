import typing as t
from pathlib import Path

from gendalf.sql.model import SQLInfo


class SQLInspector:
    def inspect_source(self, source: Path) -> t.Iterable[SQLInfo]:
        return self.inspect_paths(source.rglob("*.sql"))

    def inspect_paths(self, paths: t.Iterable[Path]) -> t.Iterable[SQLInfo]:
        for path in paths:
            yield self.inspect_path(path)

    def inspect_path(self, path: Path) -> SQLInfo:
        raise NotImplementedError
