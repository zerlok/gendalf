from __future__ import annotations

import typing as t
from collections import deque
from functools import singledispatchmethod

from sqlglot import Schema, exp
from sqlglot.optimizer.annotate_types import TypeAnnotator

T = t.TypeVar("T")


class SQLAnnotator(TypeAnnotator):
    def __init__(self, schema: Schema) -> None:
        super().__init__(schema)
        self.unknown_type = exp.DataType.build("UNKNOWN")
        self.unit_type = exp.DataType.build("UNIT", udt=True)
        self.placeholder_type = exp.DataType.build("PLACEHOLDER", udt=True)
        self.deferred = set[exp.Expression]()

    def iter_annotated(self, expressions: t.Sequence[exp.Expression]) -> t.Iterator[exp.Expression]:
        for expr in expressions:
            print("expr", type(expr), expr)
            for node in traverse_post_order(nodes=[expr], ancestors=exp.Expression.iter_expressions):
                self.annotate(node)
                print("node", type(node), node.type, node)

            yield expr

    @singledispatchmethod
    def annotate(self, node: exp.Expression) -> exp.Expression:
        if node.this is not None:
            node.type = node.this.type
        else:
            node.type = self.unknown_type.copy()

        return node

    @annotate.register
    def _annotate_data_type(self, node: exp.DataType) -> exp.DataType:
        return node

    annotate.register(TypeAnnotator._annotate_literal)

    @annotate.register
    def _annotate_identifier(self, node: exp.Identifier) -> exp.Identifier:
        parent = node.parent

        if isinstance(parent, exp.ColumnDef):
            table = self._get_table_name(parent)
            node.type = self.schema.get_column_type(table, node.this)

        elif isinstance(parent, exp.Column):
            table = parent.table
            node.type = self.schema.get_column_type(table, node.this)

        elif isinstance(parent, exp.Schema):
            table = self._get_schema_table_name(parent)
            node.type = exp.DataType(
                this=exp.DataType.Type.STRUCT,
                fields=[
                    exp.ColumnDef(
                        this=col,
                        kind=self.schema.get_column_type(table, col.this),
                        struct=True,
                    )
                    for col in parent.expressions
                ],
                nested=True,
            )

        elif isinstance(parent, exp.Table):
            node.type = exp.DataType(
                this=exp.DataType.Type.STRUCT,
                fields=[
                    exp.ColumnDef(
                        this=exp.to_identifier(column),
                        kind=self.schema.get_column_type(node.this, column),
                        struct=True,
                    )
                    for column in self.schema.column_names(node.this)
                ],
                nested=True,
            )

        else:
            raise TypeError(parent)

        return node

    # @annotate.register
    # def _annotate_table(self, node: exp.Table) -> exp.Table:
    #     # table = node.this.this.this
    #     node.type = exp.DataType(
    #         this=exp.DataType.Type.STRUCT,
    #         # expressions=[
    #         #     exp.ColumnDef(
    #         #         this=exp.to_identifier(name),
    #         #         kind=self.schema.get_column_type(table, name),
    #         #     )
    #         #     for name in self.schema.column_names(table)
    #         # ],
    #         expressions=[
    #             col if isinstance(col, exp.ColumnDef) else exp.ColumnDef(this=col.this, kind=col.type)
    #             for col in node.expressions
    #         ],
    #         nested=True,
    #     )
    #
    #     return node

    # @annotate.register
    # def _annotate_schema(self, node: exp.Schema) -> exp.Schema:
    #     # table = node.this.this.this
    #     node.type = exp.DataType(
    #         this=exp.DataType.Type.STRUCT,
    #         # expressions=[
    #         #     exp.ColumnDef(
    #         #         this=exp.to_identifier(name),
    #         #         kind=self.schema.get_column_type(table, name),
    #         #     )
    #         #     for name in self.schema.column_names(table)
    #         # ],
    #         expressions=[
    #             col if isinstance(col, exp.ColumnDef) else exp.ColumnDef(this=col.this, kind=col.type)
    #             for col in node.expressions
    #         ],
    #         nested=True,
    #     )
    #
    #     return node

    @annotate.register
    def _annotate_placeholder(self, node: exp.Placeholder) -> exp.Placeholder:
        # Context-dependent: parent has been visited last, so we are in it now
        # parent = node.parent
        #
        # if isinstance(parent, (exp.EQ, exp.NEQ, exp.LT, exp.LTE, exp.GT, exp.GTE, exp.Like, exp.ILike)):
        #     other = parent.left if parent.right is node else parent.right
        #     node.type = other.type
        #
        # else:
        #     self.deferred.add(node)
        node.type = self.placeholder_type.copy()
        return node

    # @annotate.register
    # def _annotate_column(self, node: exp.Column) -> exp.Column:
    #     node.type = node.this.type
    #
    #     return node

    @annotate.register
    def _annotate_select(self, node: exp.Select) -> exp.Select:
        node.expressions
        node.this
        raise Exception(node)

    @annotate.register
    def _annotate_tuple(self, node: exp.Tuple) -> exp.Tuple:
        node.type = exp.DataType(
            this=exp.DataType.Type.STRUCT,
            fields=[exp.ColumnDef(this=inner.this, kind=inner.type, struct=True) for inner in node.expressions],
            nested=True,
        )

        return node

    @annotate.register
    def _annotate_returning(self, node: exp.Returning) -> exp.Returning:
        node.type = exp.DataType(
            this=exp.DataType.Type.STRUCT,
            fields=[exp.ColumnDef(this=col.this, kind=col.type, struct=True) for col in node.expressions],
            nested=True,
        )

        return node

    @annotate.register
    def _annotate_insert(self, node: exp.Insert) -> exp.Insert:
        schema = node.this
        values = node.expression.expressions
        # returning = node.args.get("returning") or []

        for col, val in zip(schema.expressions, values):
            val.type = self.schema.get_column_type(schema.this.this, col.this)

        # for col in returning.expressions:
        #     col.type = self.schema.get_column_type(schema.this.this, col.this.this)

        return node

    # @annotate.register
    # def _annotate_update(self, node: exp.Update) -> exp.Update:
    #     for assignment in node.args.get("expressions", []):
    #         col = assignment.args.get("this")
    #         val = assignment.args.get("expression")
    #         col_type = self.schema.get_column_type(..., col)
    #         val.type = col_type
    #
    # @annotate.register
    # def _annotate_delete(self, node: exp.Delete) -> exp.Delete:
    #     for assignment in node.args.get("expressions", []):
    #         col = assignment.args.get("this")
    #         val = assignment.args.get("expression")
    #         col_type = self.schema.get_column_type(..., col)
    #         val.type = col_type

    # # 3) Statement handling
    # if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Copy)):
    #     self._annotate_statement(node)
    #     node.type = self.unit_type.copy()
    #     return node.type
    #
    # # 4) Expression op / function
    # if isinstance(node, exp.Func):
    #     node.type = self._annotate_function(node)
    #     return node.type
    #
    # if isinstance(node, exp.Binary):
    #     node.type = self._annotate_binary(node)
    #     return node.type
    #
    # # 5) Default: inherit from children or unit
    # node.type = node.this.type
    # return node.type

    def _annotate_function(self, node: exp.Func) -> exp.DataType:
        # Simplified: check function registry or return generic
        return self.unknown_type.copy()

    def _annotate_binary(self, node: exp.Binary) -> exp.DataType:
        if isinstance(node, (exp.EQ, exp.NEQ, exp.LT, exp.LTE, exp.GT, exp.GTE, exp.Like, exp.ILike)):
            return exp.DataType.build(exp.DataType.Type.BOOLEAN)
        return self.unknown_type.copy()

    def _get_table_name(self, node: exp.Expression) -> str:
        while not isinstance(node.this, exp.Schema):
            node = node.parent

        return self._get_schema_table_name(node.this)

    def _get_schema_table_name(self, node: exp.Schema) -> str:
        table = node.this
        assert isinstance(table, exp.Table)
        table_id = table.this
        assert isinstance(table_id, exp.Identifier)
        name = table_id.this
        assert isinstance(name, str)
        return name

    # @_extract_nested.register
    # def _extract_nested_schema(self, node: exp.Schema) -> t.Sequence[exp.Expression]:
    #     return []

    # def _extract_nested(self, node: exp.Expression) -> t.Sequence[exp.Expression]:
    #     ancestors = list[exp.Expression]()
    #
    #     for key, value in node.args.items():
    #         if isinstance(value, exp.Expression):
    #             ancestors.append(value)
    #
    #         elif isinstance(value, t.Iterable):
    #             ancestors.extend(item for item in value if isinstance(item, exp.Expression))
    #
    #     return ancestors


def traverse_post_order(
    *,
    nodes: t.Sequence[T],
    ancestors: t.Callable[[T], t.Iterable[T]],
) -> t.Iterable[T]:
    stack = deque[tuple[T, bool]]([(node, False) for node in nodes])
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
                (ancestor, False) for ancestor in ancestors(node) if ancestor is not node and ancestor not in visited
            )
