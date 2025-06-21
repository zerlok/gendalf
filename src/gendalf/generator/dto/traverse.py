from __future__ import annotations

import typing as t
from collections import deque

A = t.TypeVar("A")
B = t.TypeVar("B")


def ident(obj: A) -> A:
    return obj


def truthy(_: object) -> bool:
    return True


def traverse_post_order(
    nodes: t.Sequence[A],
    ancestors: t.Callable[[B], t.Sequence[A]],
    transform: t.Callable[[A], B] = ident,
    predicate: t.Callable[[A], bool] = truthy,
) -> t.Iterable[B]:
    stack = deque[tuple[A, B, bool]]([(node, transform(node), False) for node in nodes if predicate(node)])
    visited = set[A]()

    while stack:
        node, result, processed = stack.pop()
        if node in visited:
            continue

        if processed:
            visited.add(node)
            yield result

        else:
            stack.append((node, result, True))

            for ancestor in reversed(ancestors(result)):
                if ancestor is not node and ancestor not in visited and predicate(ancestor):
                    stack.append((ancestor, transform(ancestor), False))
