from __future__ import annotations

import typing as t
from dataclasses import dataclass, field, replace
from functools import singledispatchmethod

from sqlglot import Dialect, MappingSchema, Schema, exp

from gendalf.traverse import DfsPostOrderTraversal, TraverseScope, TraverseStrategy


class SQLAnnotator:
    def __init__(self, dialect: Dialect) -> None:
        self.__dialect = dialect

    def annotate(self, expressions: t.Sequence[exp.Expression]) -> t.Iterable[exp.Expression]:
        schema = self._build_schema(expressions)
        traversal = DfsPostOrderTraversal(ExpressionTraverseBasedAnnotator(schema))

        for expression in expressions:
            print("\n ---------------- EXPRESSION --------------- \n", type(expression), expression)

            annotated_expr = expression.copy()
            for annotated in traversal.traverse(annotated_expr):
                print(type(annotated.node), annotated.type_, annotated.node)
                annotated.node.type = annotated.type_

            yield annotated_expr

    def _build_schema(self, expressions: t.Sequence[exp.Expression]) -> Schema:
        schema = MappingSchema()

        for expression in expressions:
            if (
                not isinstance(expression, exp.Create)
                or not isinstance(expression.this, exp.Schema)
                or not isinstance(expression.this.this, exp.Table)
            ):
                continue

            schema_expr: exp.Schema = expression.this
            table_expr: exp.Table = expression.this.this

            schema.add_table(
                table=table_expr,
                column_mapping={
                    col: self._get_column_type(col) for col in schema_expr.expressions if isinstance(col, exp.ColumnDef)
                },
            )

        return schema

    def _get_column_type(self, node: exp.ColumnDef) -> exp.DataType:
        if "nullable" not in node.kind.args:
            nullable = not any(
                isinstance(c.kind, (exp.PrimaryKeyColumnConstraint, exp.NotNullColumnConstraint))
                for c in node.constraints
            )

            dtype = node.kind.copy()
            dtype.set("nullable", nullable)

        else:
            dtype = node.kind

        return dtype

    # def _apply_annotation(self, annotated: Annotated) -> None:
    #     if not annotated.signatures:
    #         return
    #
    #     candidates = list[Signature]()
    #     for signature in annotated.signatures:
    #         # TODO: also validate type var lower bounds
    #         if all(
    #             operand.type.is_type(param, check_nullable=True)
    #             for param, operand in zip(signature.parameters, annotated.operands)
    #             if not isinstance(operand, exp.Placeholder)
    #         ):
    #             candidates.append(signature)
    #
    #     if not candidates:
    #         warnings.warn("no candidates found", RuntimeWarning)
    #         return
    #
    #     annotated.node.type = (
    #         build_type("Union", [candidate.returns for candidate in candidates])
    #         if len(candidates) > 1
    #         else candidates[0].returns
    #     )
    #
    #     for idx, operand in enumerate(annotated.operands):
    #         if isinstance(operand.type, exp.Placeholder):
    #             # TODO: move lower bound up
    #             operand.type = (
    #                 build_type("Union", [candidate.parameters[idx] for candidate in candidates])
    #                 if len(candidates) > 1
    #                 else candidates[0].parameters[idx]
    #             )
    #             # operand.type.set_type_var_bounds([candidate.parameters[idx] for candidate in candidates])


@dataclass()
class ExpressionScope:
    table: str = field(default="")
    columns: t.Mapping[str, exp.DataType] = field(default_factory=dict)
    typer: t.Union[exp.DataType, t.Callable[[], exp.DataType], None] = field(default=None)


@dataclass(frozen=True, kw_only=True)
class Annotated:
    node: exp.Expression
    type_: exp.DataType


class ExpressionTraverseBasedAnnotator(TraverseStrategy[exp.Expression, ExpressionScope, Annotated]):
    def __init__(self, schema: Schema) -> None:
        self.__schema = schema

    def filter(self, node: exp.Expression, parent: t.Optional[TraverseScope[exp.Expression, ExpressionScope]]) -> bool:
        return not isinstance(
            node,
            (
                exp.Identifier,
                exp.ColumnConstraint,
                exp.ColumnConstraintKind,
                exp.DataType,
                exp.DataTypeParam,
                exp.Alias,
                exp.TableAlias,
                exp.Create,
                exp.Alter,
            ),
        )

    def enter(
        self,
        node: exp.Expression,
        parent: t.Optional[TraverseScope[exp.Expression, ExpressionScope]],
    ) -> ExpressionScope:
        parent_scope = parent.entered if parent is not None else ExpressionScope()
        node_scope = self._enter_node(node, parent_scope)

        return node_scope if node_scope is not None else parent_scope

    def descendants(
        self,
        node: exp.Expression,
        entered: ExpressionScope,
        parent: t.Optional[TraverseScope[exp.Expression, ExpressionScope]],
    ) -> t.Iterable[exp.Expression]:
        return node.iter_expressions()

    def leave(
        self,
        node: exp.Expression,
        entered: ExpressionScope,
        parent: t.Optional[TraverseScope[exp.Expression, ExpressionScope]],
    ) -> Annotated:
        return Annotated(
            node=node,
            type_=entered.typer() if callable(entered.typer) else entered.typer,
        )

    @singledispatchmethod
    def _enter_node(self, node: exp.Expression, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        msg = "unsupported expression"
        raise TypeError(msg, node, scope)

    @_enter_node.register
    def _enter_schema(
        self,
        node: t.Union[exp.ColumnDef, exp.Table, exp.Schema],
        scope: ExpressionScope,
    ) -> t.Optional[ExpressionScope]:
        return None

    @_enter_node.register
    def _enter_this(
        self,
        node: t.Union[
            exp.From,
            exp.Where,
            exp.Group,
            exp.Having,
        ],
        scope: ExpressionScope,
    ) -> t.Optional[ExpressionScope]:
        def get_this_type() -> exp.DataType:
            return node.this.type

        return replace(scope, typer=get_this_type)

    @_enter_node.register
    def _enter_int(
        self,
        node: t.Union[exp.Limit, exp.Offset],
        scope: ExpressionScope,
    ) -> t.Optional[ExpressionScope]:
        return replace(scope, typer=exp.DataType(this=exp.DataType.Type.INT))

    @_enter_node.register
    def _enter_array(
        self,
        node: t.Union[exp.Array, exp.Values],
        scope: ExpressionScope,
    ) -> t.Optional[ExpressionScope]:
        def build_array_type() -> exp.DataType:
            return exp.DataType.build(
                dtype=exp.DataType.Type.ARRAY,
                expressions=[exp.DataTypeParam(this=node.expressions[0].type)],
            )

        return replace(scope, typer=build_array_type)

    @_enter_node.register
    def _enter_tuple(self, node: exp.Tuple, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        def build_tuple_type() -> exp.DataType:
            return exp.DataType.build(
                dtype="Tuple",
                expressions=[inner.type for inner in node.expressions],
                udt=True,
            )

        return replace(scope, typer=build_tuple_type)

    @_enter_node.register
    def _enter_literal(self, node: exp.Literal, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        if node.is_int:
            dtype = exp.DataType.Type.INT

        elif node.is_number:
            dtype = exp.DataType.Type.DOUBLE

        elif node.is_string:
            dtype = exp.DataType.Type.TEXT

        else:
            msg = "unknown literal value type"
            raise TypeError(msg, node)

        return replace(scope, typer=exp.DataType(this=dtype))

    @_enter_node.register
    def _enter_current_timestamp(
        self,
        node: exp.CurrentTimestamp,
        scope: ExpressionScope,
    ) -> t.Optional[ExpressionScope]:
        return replace(scope, typer=exp.DataType(this=exp.DataType.Type.TIMESTAMPTZ))

    @_enter_node.register
    def _enter_column(self, node: exp.Column, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        table = node.table
        column = self._get_this_name(node)

        if table:
            dtype = self.__schema.get_column_type(table, column)

        elif scope is not None:
            dtype = scope.columns.get(column)

        else:
            dtype = None

        return replace(scope, typer=dtype)

    @_enter_node.register
    def _enter_returning(self, node: exp.Returning, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        return replace(
            scope,
            typer=exp.DataType(
                this=exp.DataType.Type.STRUCT,
                expressions=[
                    exp.ColumnDef(
                        this=exp.to_identifier(col.name),
                        kind=self.__schema.get_column_type(col.table, col.name)
                        if col.table
                        else scope.columns.get(col.name),
                    )
                    for col in node.expressions
                ],
            ),
        )

    @_enter_node.register
    def _enter_select(self, node: exp.Select, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        # TODO: WHERE block
        # TODO: GROUP BY block
        # TODO: HAVING block

        from_ = node.args.get("from")
        if isinstance(from_, exp.From):
            scope = self._build_scope(from_, scope)

        def build_select_type() -> exp.DataType:
            # TODO: alias => column => from
            return exp.DataType(
                this=exp.DataType.Type.STRUCT,
                expressions=[
                    exp.ColumnDef(
                        this=exp.to_identifier(col.name),
                        kind=self.__schema.get_column_type(col.table, col.name)
                        if col.table
                        else scope.columns.get(col.name),
                    )
                    for col in node.expressions
                ],
            )

        return replace(scope, typer=build_select_type)

    @_enter_node.register
    def _enter_insert(self, node: exp.Insert, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        # TODO: FROM block
        # TODO: WHERE block
        scope = self._build_scope(node, scope)

        returning = node.args.get("returning")
        if isinstance(returning, exp.Returning):
            node.type = returning.type

        def build_insert_type() -> t.Optional[exp.DataType]:
            return returning.type if returning is not None else None

        return replace(scope, typer=build_insert_type)

    @_enter_node.register
    def _enter_update(self, node: exp.Update, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        # TODO: SET block
        # TODO: WHERE block
        scope = self._build_scope(node, scope)

        returning = node.args.get("returning")
        if isinstance(returning, exp.Returning):
            node.type = returning.type

        def build_update_type() -> t.Optional[exp.DataType]:
            return returning.type if returning is not None else None

        return replace(scope, typer=build_update_type)

    @_enter_node.register
    def _enter_delete(self, node: exp.Delete, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        # TODO: WHERE block
        scope = self._build_scope(node, scope)

        returning = node.args.get("returning")
        if isinstance(returning, exp.Returning):
            node.type = returning.type

        def build_update_type() -> t.Optional[exp.DataType]:
            return returning.type if returning is not None else None

        return replace(scope, typer=build_update_type)

    @_enter_node.register
    def _enter_cast(self, node: exp.Cast, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        return replace(scope, typer=node.to)

    @_enter_node.register
    def _enter_placeholder(self, node: exp.Placeholder, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        # return replace(
        #     scope,
        #     dtype=build_type("TypeVar", [node.copy()]),
        #     placeholders=[node],
        # )
        parent = node.parent
        assert isinstance(parent, exp.Cast)
        return replace(scope, typer=parent.to)

    @_enter_node.register
    def _enter_function(self, node: exp.Func, scope: ExpressionScope) -> t.Optional[ExpressionScope]:
        # Simplified: check function registry or return generic
        raise NotImplementedError(node)

    @_enter_node.register
    def _enter_binary_bool(
        self,
        node: t.Union[
            exp.EQ,
            exp.NEQ,
            exp.LT,
            exp.LTE,
            exp.GT,
            exp.GTE,
            exp.Like,
            exp.ILike,
        ],
        scope: ExpressionScope,
    ) -> t.Optional[ExpressionScope]:
        return replace(scope, typer=exp.DataType(this=exp.DataType.Type.BOOLEAN))

    def _build_scope(
        self,
        node: exp.Expression,
        parent: ExpressionScope,
        columns: t.Optional[t.Sequence[exp.Expression]] = None,
    ) -> ExpressionScope:
        table = self._get_this_name(node)
        column_names: t.Sequence[str] = (
            [self._get_this_name(col) for col in columns if isinstance(col, (exp.Identifier, exp.Column))]
            if columns
            else self.__schema.column_names(table)
        )

        return replace(
            parent,
            table=table,
            columns={col: self.__schema.get_column_type(table, col) for col in column_names},
        )

    def _get_this_name(self, node: exp.Expression) -> str:
        this_id = node

        while not isinstance(this_id, exp.Identifier) and this_id is not None:
            this_id = this_id.this

        if this_id is None:
            msg = "can't get name"
            raise ValueError(msg, node)

        return this_id.this
