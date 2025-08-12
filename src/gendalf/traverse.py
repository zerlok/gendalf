from __future__ import annotations

import typing as t
from collections import deque

T = t.TypeVar("T")
A = t.TypeVar("A")
B = t.TypeVar("B")


def truthy(_: object) -> bool:
    return True


def traverse_dfs_pre_order(
    nodes: t.Sequence[T],
    ancestors: t.Callable[[T], t.Iterable[T]],
    predicate: t.Callable[[T], bool] = truthy,
) -> t.Iterable[T]:
    stack = deque[T]([node for node in nodes if predicate(node)])

    while stack:
        node = stack.pop()
        stack.extend(ancestor for ancestor in ancestors(node) if predicate(ancestor))
        yield node


def traverse_dfs_post_order(
    nodes: t.Sequence[T],
    ancestors: t.Callable[[T], t.Iterable[T]],
    predicate: t.Callable[[T], bool] = truthy,
) -> t.Iterable[T]:
    stack = deque[tuple[T, bool]]([(node, False) for node in nodes if predicate(node)])
    visited = set[T]()

    while stack:
        node, processed = stack.pop()
        if node in visited:
            continue

        if processed:
            visited.add(node)
            yield node

        else:
            stack.append((node, True))
            stack.extend(
                (ancestor, False)
                for ancestor in ancestors(node)
                if ancestor is not node and ancestor not in visited and predicate(ancestor)
            )


def traverse_dfs_post_order_map(
    nodes: t.Sequence[A],
    transform: t.Callable[[A], B],
    ancestors: t.Callable[[B], t.Iterable[A]],
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
            stack.extend(
                (ancestor, transform(ancestor), False)
                for ancestor in ancestors(result)
                if ancestor is not node and ancestor not in visited and predicate(ancestor)
            )


def ident(obj: A) -> A:
    return obj
