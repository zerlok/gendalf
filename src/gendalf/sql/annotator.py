from __future__ import annotations

import typing as t
from functools import singledispatchmethod

from sqlglot import Schema, exp

from gendalf.traverse import traverse_dfs_post_order

T = t.TypeVar("T")


class SQLAnnotator:
    def __init__(self, schema: Schema) -> None:
        self.__schema = schema
        self.__unknown_type = exp.DataType.build("UNKNOWN")
        self.__unit_type = exp.DataType.build("UNIT", udt=True)

    def annotate(self, expression: exp.Expression) -> exp.Expression:
        # print("\n ---------------- EXPRESSION --------------- \n", type(expression), expression)
        for node in traverse_dfs_post_order(nodes=[expression], ancestors=exp.Expression.iter_expressions):
            self._annotate(node)
            # print(f"node {type(node)} : {node.type} : '{node}'")

        return expression

    @singledispatchmethod
    def _annotate(self, node: exp.Expression) -> None:
        msg = "unsupported expression"
        raise TypeError(msg, node)

    @_annotate.register
    def _ignore_annotation(
        self,
        node: t.Union[
            exp.Identifier,
            exp.ColumnConstraint,
            exp.ColumnConstraintKind,
            exp.DataType,
            exp.DataTypeParam,
            exp.Alias,
            exp.TableAlias,
        ],
    ) -> None:
        pass

    @_annotate.register
    def _annotate_as_unit(self, node: t.Union[exp.Create, exp.Alter]) -> None:
        self._set_type(node, self.__unit_type)

    @_annotate.register
    def _annotate_as_this(
        self,
        node: t.Union[
            exp.From,
            exp.Where,
            exp.Group,
            exp.Having,
        ],
    ) -> None:
        self._set_type(node, node.this.type)

    @_annotate.register
    def _annotate_as_int(self, node: t.Union[exp.Limit, exp.Offset]) -> None:
        self._set_type(node, exp.DataType.Type.INT)
        self._resolve_placeholders(node, exp.DataType.Type.INT)

    @_annotate.register
    def _annotate_literal(self, node: exp.Literal) -> None:
        if isinstance(node.this, str):
            self._set_type(node, exp.DataType.Type.TEXT)

        elif isinstance(node.this, float):
            self._set_type(node, exp.DataType.Type.DOUBLE)

        elif isinstance(node.this, int):
            self._set_type(node, exp.DataType.Type.INT)

        elif isinstance(node.this, bool):
            self._set_type(node, exp.DataType.Type.BOOLEAN)

        elif node.this is None:
            # TODO: set type var => Null(T) and infer T from AST.
            # self._set_type_var(node, [])
            self._set_type(node, exp.DataType.Type.NULL)

        else:
            msg = "unknown literal value type"
            raise TypeError(msg, node)

    @_annotate.register
    def _annotate_current_timestamp(self, node: exp.CurrentTimestamp) -> None:
        self._set_type(node, exp.DataType.Type.TIMESTAMP)

    @_annotate.register
    def _annotate_column(self, node: exp.Column) -> None:
        schema = node

        # FIXME: make it work for columns in where clause in select statement
        while not isinstance(schema.this, exp.Schema):
            schema = schema.parent

        table = self._get_table_name(schema.this)
        self._set_type(node, self.__schema.get_column_type(table, node.this))

    @_annotate.register
    def _annotate_column_def(self, node: exp.ColumnDef) -> None:
        schema = node

        while not isinstance(schema, (exp.Schema, exp.Table)):
            schema = schema.parent

        table = self._get_table_name(schema)
        self._set_type(node, self.__schema.get_column_type(table, node.this))

    @_annotate.register
    def _annotate_table(self, node: exp.Table) -> None:
        table = self._get_table_name(node)
        self._set_struct_type(
            node,
            [
                exp.ColumnDef(this=exp.to_identifier(column), kind=self.__schema.get_column_type(table, column))
                for column in self.__schema.column_names(table)
            ],
        )

    @_annotate.register
    def _annotate_schema(self, node: exp.Schema) -> None:
        table = self._get_table_name(node)
        self._set_struct_type_from_expressions(table, node)

    @_annotate.register
    def _annotate_placeholder(self, node: exp.Placeholder) -> None:
        self._set_type_var(node, node.copy())

    @_annotate.register
    def _annotate_tuple(self, node: exp.Tuple) -> None:
        self._set_type(node, "Tuple", [inner.type for inner in node.expressions])

    @_annotate.register
    def _annotate_array(self, node: exp.Array) -> None:
        self._set_type(node, exp.DataType.Type.ARRAY, [inner.type for inner in node.expressions])

    @_annotate.register
    def _annotate_values(self, node: exp.Values) -> None:
        self._set_type(node, exp.DataType.Type.ARRAY, [inner.type for inner in node.expressions])

    @_annotate.register
    def _annotate_returning(self, node: exp.Returning) -> None:
        schema = node

        while not isinstance(schema.this, (exp.Schema, exp.Table)):
            schema = schema.parent

        table = self._get_table_name(schema.this)
        self._set_struct_type_from_expressions(table, node)

    @_annotate.register
    def _annotate_select(self, node: exp.Select) -> None:
        from_ = node.args.get("from")
        # alias => column => from
        if isinstance(from_, exp.From):
            columns = self._get_struct_columns(from_)
            self._set_struct_type(
                node,
                [
                    exp.ColumnDef(this=exp.to_identifier(col.alias_or_name), kind=columns[self._get_column_name(col)])
                    for col in node.expressions
                    if isinstance(col, (exp.Column, exp.Alias))
                ],
            )

        # where = node.args.get("where")
        # if where is not None:
        #     self._resolve_placeholders(where, from_)

    @_annotate.register
    def _annotate_insert(self, node: exp.Insert) -> None:
        # TODO: check where part
        schema = node.this
        values = node.expression.expressions

        for val in values:
            self._resolve_placeholders(val, schema.type)

        returning = node.args.get("returning")
        if isinstance(returning, exp.Returning):
            node.type = returning.type

    @_annotate.register
    def _annotate_update(self, node: exp.Update) -> None:
        # TODO: check where part
        for assign in node.expressions:
            self._resolve_placeholders(assign, assign.this.type)

    @_annotate.register
    def _annotate_delete(self, node: exp.Delete) -> None:
        # TODO: check where part
        returning = node.args.get("returning")
        if isinstance(returning, exp.Returning):
            node.type = returning.type

    @_annotate.register
    def _annotate_function(self, node: exp.Func) -> None:
        # Simplified: check function registry or return generic
        raise NotImplementedError(node)

    # TODO: support more operators and more type inference cases
    @_annotate.register
    def _annotate_binary(self, node: exp.Binary) -> None:
        if isinstance(node, (exp.EQ, exp.NEQ, exp.LT, exp.LTE, exp.GT, exp.GTE, exp.Like, exp.ILike)):
            node.type = exp.DataType(this=exp.DataType.Type.BOOLEAN)
            # case 1: right has placeholders => infer type from left type + binary operator signature
            self._resolve_placeholders(node.right, node.left.type)
            # case 2: left has placeholders => infer type from right type + binary operator signature
            # ...
            # case 3: left and right has placeholders => infer type from binary operator signature
            # ...
            # case 4: assign type vars to operator
            # ...

    def _set_type(
        self,
        node: exp.Expression,
        dtype: t.Optional[t.Union[str, exp.DataType, exp.DataType.Type]],
        params: t.Optional[t.Sequence[exp.Expression]] = None,
    ) -> None:
        if dtype is not None:
            node.type = exp.DataType.build(
                dtype=dtype,
                expressions=[exp.DataTypeParam(this=param) for param in (params or ())],
                udt=isinstance(dtype, str),
            )

        else:
            raise ValueError(node.parent.parent, type(node), node)
            node.type = self.__unknown_type.copy()

    def _set_type_var(self, node: exp.Expression, *params: exp.Expression) -> None:
        self._set_type(node, "TypeVar", params)

    def _set_struct_type(self, node: exp.Expression, columns: t.Sequence[exp.ColumnDef]) -> None:
        self._set_type(node, exp.DataType(this=exp.DataType.Type.STRUCT, expressions=columns))

    def _set_struct_type_from_expressions(self, table: str, node: exp.Expression) -> None:
        self._set_struct_type(
            node,
            [
                self._build_column_def(table, col)
                for col in node.expressions
                if isinstance(col, (exp.Identifier, exp.Column, exp.ColumnDef))
            ],
        )

    def _build_column_def(self, table: str, node: exp.Expression) -> exp.ColumnDef:
        if isinstance(node, exp.Identifier):
            this = node
            kind = self.__schema.get_column_type(table, node.this)

        elif isinstance(node, exp.Column):
            this = self._get_column_id(node)
            kind = self.__schema.get_column_type(table, self._get_column_name(node))

        elif isinstance(node, exp.ColumnDef):
            this = node.this
            kind = node.kind

        else:
            this = node.this
            kind = node.type

        return exp.ColumnDef(this=this, kind=kind)

    def _get_table_id(self, node: exp.Expression) -> exp.Identifier:
        while not isinstance(node, exp.Table):
            node = node.this

        table_id = node.this
        assert isinstance(table_id, exp.Identifier)

        return table_id

    def _get_table_name(self, node: exp.Expression) -> str:
        table_id = self._get_table_id(node)

        name = table_id.this
        assert isinstance(name, str)

        return name

    def _get_column_id(self, node: exp.Expression) -> exp.Identifier:
        while not isinstance(node, exp.Column):
            node = node.this

        col_id = node.this
        assert isinstance(col_id, exp.Identifier)

        return col_id

    def _get_column_name(self, node: exp.Expression) -> str:
        col_id = self._get_column_id(node)
        name = col_id.this
        assert isinstance(name, str)

        return name

    def _get_struct_columns(self, node: exp.Expression) -> t.Mapping[str, exp.DataType]:
        assert node.type.is_type(exp.DataType.Type.STRUCT)
        return {col.name: col.kind for col in node.type.expressions if isinstance(col, exp.ColumnDef)}

    def _resolve_placeholders(self, expr: exp.Expression, dtype: t.Union[exp.DataType, exp.DataType.Type]) -> None:
        if isinstance(expr, exp.Placeholder):
            self._set_type(expr, dtype)

        elif expr.expression is not None:
            self._set_type(expr.expression, dtype)

        else:
            for node, col in zip(expr.expressions, dtype.expressions):
                if isinstance(node, exp.Placeholder):
                    self._set_type(node, col.kind)
