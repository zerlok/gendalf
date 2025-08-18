from __future__ import annotations

import abc
import typing as t
from collections import deque
from dataclasses import dataclass, replace

T = t.TypeVar("T")
A = t.TypeVar("A")
B = t.TypeVar("B")
E = t.TypeVar("E")
L = t.TypeVar("L")


@dataclass(frozen=True, kw_only=True)
class TraverseScope(t.Generic[T, E]):
    node: T
    entered: E
    parent: t.Optional[TraverseScope[T, E]]


@dataclass(frozen=True, kw_only=True)
class TraverseContext(t.Generic[T, E]):
    node: T
    parent: t.Optional[TraverseScope[T, E]] = None
    entered: bool = False


class TraverseStrategy(t.Generic[T, E, L], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def filter(self, node: T, parent: t.Optional[TraverseScope[T, E]]) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def enter(self, node: T, parent: t.Optional[TraverseScope[T, E]]) -> E:
        raise NotImplementedError

    @abc.abstractmethod
    def descendants(self, node: T, entered: E, parent: t.Optional[TraverseScope[T, E]]) -> t.Iterable[T]:
        raise NotImplementedError

    @abc.abstractmethod
    def leave(self, node: T, entered: E, parent: t.Optional[TraverseScope[T, E]]) -> L:
        raise NotImplementedError


class Traversal(t.Generic[A, B], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def traverse(self, *nodes: A) -> t.Iterable[B]:
        raise NotImplementedError


class DfsPostOrderTraversal(t.Generic[T, E, L], Traversal[T, L]):
    def __init__(self, strategy: TraverseStrategy[T, E, L]) -> None:
        self.__strategy = strategy

    def traverse(self, *nodes: T) -> t.Iterable[L]:
        processed = set[T]()
        scopes = dict[T, TraverseScope[T, E]]()

        stack = deque[TraverseContext[T, E]](
            TraverseContext(node=node) for node in nodes if self.__strategy.filter(node, None)
        )

        while stack:
            context = stack.pop()
            if context.node in processed:
                continue

            if context.entered:
                scope = scopes.pop(context.node)
                left = self.__strategy.leave(scope.node, scope.entered, scope.parent)
                processed.add(context.node)

                yield left

            else:
                entered = self.__strategy.enter(context.node, context.parent)
                scope = scopes[context.node] = TraverseScope(node=context.node, entered=entered, parent=context.parent)
                stack.append(replace(context, entered=True))

                stack.extend(
                    TraverseContext(node=descendant, parent=scope)
                    for descendant in self.__strategy.descendants(context.node, entered, context.parent)
                    if self.__strategy.filter(descendant, scope)
                    and descendant is not context.node
                    and descendant not in processed
                )


class DfsPreOrderTraversal(t.Generic[T, E], Traversal[T, E]):
    def __init__(self, strategy: TraverseStrategy[T, E, object]) -> None:
        self.__strategy = strategy

    def traverse(self, *nodes: A) -> t.Iterable[B]:
        queue = deque[TraverseContext[T, E]](
            TraverseContext(node=node) for node in nodes if self.__strategy.filter(node, None)
        )
        scopes = dict[T, TraverseScope[T, E]]()

        while queue:
            context = queue.pop()
            if context.entered:
                scope = scopes.pop(context.node)
                self.__strategy.leave(scope.node, scope.entered, scope.parent)

            else:
                entered = self.__strategy.enter(context.node, context.parent)
                scope = scopes[context.node] = TraverseScope(node=context.node, entered=entered, parent=context.parent)

                queue.extend(
                    TraverseContext(node=descendant, parent=scope)
                    for descendant in self.__strategy.descendants(context.node, entered, context.parent)
                    if self.__strategy.filter(descendant, scope)
                )
                queue.append(replace(context, entered=True))

                yield entered


class IdentStrategy(t.Generic[T], TraverseStrategy[T, T, T]):
    def __init__(
        self, descendants: t.Callable[[T], t.Iterable[T]], predicate: t.Optional[t.Callable[[T], bool]]
    ) -> None:
        self.__descendants = descendants
        self.__predicate = predicate

    def filter(self, node: T, parent: t.Optional[TraverseScope[T, T]]) -> bool:
        return self.__predicate(node) if self.__predicate is not None else True

    def enter(self, node: T, parent: t.Optional[TraverseScope[T, T]]) -> T:
        return node

    def descendants(self, node: T, entered: T, parent: t.Optional[TraverseScope[T, T]]) -> t.Iterable[T]:
        return self.__descendants(node)

    def leave(self, node: T, entered: T, parent: t.Optional[TraverseScope[T, T]]) -> T:
        return node


class EnterStrategy(t.Generic[T, E], TraverseStrategy[T, E, E]):
    def __init__(
        self,
        enter: t.Callable[[T], E],
        descendants: t.Callable[[E], t.Iterable[T]],
        predicate: t.Optional[t.Callable[[T], bool]],
    ) -> None:
        self.__enter = enter
        self.__descendants = descendants
        self.__predicate = predicate

    def filter(self, node: T, parent: t.Optional[TraverseScope[T, E]]) -> bool:
        return self.__predicate(node) if self.__predicate is not None else True

    def enter(self, node: T, parent: t.Optional[TraverseScope[T, E]]) -> E:
        return self.__enter(node)

    def descendants(self, node: T, entered: E, parent: t.Optional[TraverseScope[T, E]]) -> t.Iterable[T]:
        return self.__descendants(entered)

    def leave(self, node: T, entered: E, parent: t.Optional[TraverseScope[T, E]]) -> None:
        return entered


def traverse_dfs_pre_order(
    nodes: t.Sequence[T],
    descendant: t.Callable[[T], t.Iterable[T]],
    predicate: t.Optional[t.Callable[[T], bool]] = None,
) -> t.Iterable[T]:
    return DfsPreOrderTraversal(IdentStrategy(descendant, predicate)).traverse(*nodes)


def traverse_dfs_post_order(
    nodes: t.Sequence[T],
    descendant: t.Callable[[T], t.Iterable[T]],
    predicate: t.Optional[t.Callable[[T], bool]] = None,
) -> t.Iterable[T]:
    return DfsPostOrderTraversal(IdentStrategy(descendant, predicate)).traverse(*nodes)


def traverse_dfs_post_order_map(
    nodes: t.Sequence[A],
    transform: t.Callable[[A], B],
    descendant: t.Callable[[B], t.Iterable[A]],
    predicate: t.Optional[t.Callable[[A], bool]] = None,
) -> t.Iterable[B]:
    return DfsPostOrderTraversal(EnterStrategy(transform, descendant, predicate)).traverse(*nodes)
