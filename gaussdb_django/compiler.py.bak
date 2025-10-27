from django.db.models.sql.compiler import (
    SQLAggregateCompiler,
    SQLCompiler,
    SQLDeleteCompiler,
)
from django.db.models.sql.compiler import SQLInsertCompiler as BaseSQLInsertCompiler
from django.db.models.sql.compiler import SQLUpdateCompiler
from django.db.models.sql.compiler import SQLCompiler as BaseSQLCompiler
from django.db.models.functions import JSONArray, JSONObject
from django.db.models import IntegerField, FloatField, Func


__all__ = [
    "SQLAggregateCompiler",
    "SQLCompiler",
    "SQLDeleteCompiler",
    "SQLInsertCompiler",
    "SQLUpdateCompiler",
    "GaussDBSQLCompiler",
]


class InsertUnnest(list):
    """
    Sentinel value to signal DatabaseOperations.bulk_insert_sql() that the
    UNNEST strategy should be used for the bulk insert.
    """

    def __str__(self):
        return "UNNEST(%s)" % ", ".join(self)


class SQLInsertCompiler(BaseSQLInsertCompiler):
    def assemble_as_sql(self, fields, value_rows):
        return super().assemble_as_sql(fields, value_rows)

    def as_sql(self):
        return super().as_sql()


class GaussDBSQLCompiler(BaseSQLCompiler):
    def __repr__(self):
        base = super().__repr__()
        return base.replace("GaussDBSQLCompiler", "SQLCompiler")

    def compile(self, node, force_text=False):
        if isinstance(node, Func):
            func_name = getattr(node, "function", None)
            if func_name is None:
                node.function = "json_build_object"
        if node.__class__.__name__ == "OrderBy":
            node.expression.is_ordering = True

        if isinstance(node, JSONArray):
            return self._compile_json_array(node)

        elif isinstance(node, JSONObject):
            return self._compile_json_object(node)

        elif node.__class__.__name__ == "KeyTransform":
            if getattr(node, "function", None) is None:
                node.function = "json_extract_path_text"
            return self._compile_key_transform(node, force_text=force_text)
        elif node.__class__.__name__ == "Cast":
            return self._compile_cast(node)
        elif node.__class__.__name__ == "HasKey":
            return self._compile_has_key(node)
        elif node.__class__.__name__ == "HasKeys":
            return self._compile_has_keys(node)
        elif node.__class__.__name__ == "HasAnyKeys":
            return self._compile_has_any_keys(node)

        return super().compile(node)

    def _compile_json_array(self, node):
        if not getattr(node, "source_expressions", None):
            return "'[]'::json", []
        params = []
        sql_parts = []
        for arg in node.source_expressions:
            arg_sql, arg_params = self.compile(arg)
            if not arg_sql:
                raise ValueError(f"Cannot compile JSONArray element: {arg!r}")
            sql_parts.append(arg_sql)
            params.extend(arg_params)

        sql = f"json_build_array({', '.join(sql_parts)})"
        return sql, params

    def _compile_json_object(self, node):
        expressions = getattr(node, "source_expressions", []) or []
        if not expressions:
            return "'{}'::json", []
        sql_parts = []
        params = []
        if len(expressions) % 2 != 0:
            raise ValueError(
                "JSONObject requires even number of arguments (key-value pairs)"
            )
        for i in range(0, len(expressions), 2):
            key_expr = expressions[i]
            val_expr = expressions[i + 1]
            key_sql, key_params = self.compile(key_expr)
            val_sql, val_params = self.compile(val_expr)

            key_value = getattr(key_expr, "value", None)
            if isinstance(key_value, str):
                key_sql = f"""'{key_value.replace("'", "''")}'"""
                key_params = []

            if not key_sql or not val_sql:
                raise ValueError(
                    f"Cannot compile key/value pair: {key_expr}, {val_expr}"
                )

            sql_parts.append(f"{key_sql}, {val_sql}")
            params.extend(key_params + val_params)
        sql = f"json_build_object({', '.join(sql_parts)})"
        return sql, params

    def _compile_key_transform(self, node, force_text=False):
        def collect_path(n):
            path = []
            while n.__class__.__name__ == "KeyTransform":
                key_expr = getattr(n, "key", None) or getattr(n, "path", None)
                lhs = getattr(n, "lhs", None)

                if isinstance(lhs, JSONObject) and key_expr is None:
                    key_node = lhs.source_expressions[0]
                    key_expr = getattr(key_node, "value", key_node)

                if key_expr is None:
                    if lhs.__class__.__name__ == "KeyTransform":
                        lhs, sub_path = collect_path(lhs)
                        path.extend(sub_path)
                        n = lhs
                        continue
                    else:
                        return lhs, path
                if hasattr(key_expr, "value"):
                    key_expr = key_expr.value
                path.append(key_expr)
                n = lhs

            return n, list(reversed(path))

        base_lhs, path = collect_path(node)

        if isinstance(base_lhs, JSONObject):
            lhs_sql, lhs_params = self._compile_json_object(base_lhs)
            current_type = "object"
        elif isinstance(base_lhs, JSONArray):
            lhs_sql, lhs_params = self._compile_json_array(base_lhs)
            current_type = "array"
        elif isinstance(base_lhs, Func):
            return super().compile(node)
        else:
            lhs_sql, lhs_params = super().compile(base_lhs)
            current_type = "scalar"
        sql = lhs_sql
        numeric_fields = (IntegerField, FloatField)

        for i, k in enumerate(path):
            is_last = i == len(path) - 1

            if current_type in ("object", "array"):
                if is_last and (
                    force_text
                    or getattr(node, "_function_context", False)
                    or getattr(node, "is_ordering", False)
                    or isinstance(getattr(node, "output_field", None), numeric_fields)
                ):
                    cast = (
                        "numeric"
                        if isinstance(
                            getattr(node, "output_field", None), numeric_fields
                        )
                        else "text"
                    )
                    if current_type == "object":
                        sql = f"({sql}->>'{k}')::{cast}"
                    else:
                        sql = f"({sql}->'{k}')::{cast}"
                else:
                    sql = f"{sql}->'{k}'"
                current_type = "unknown"
            else:
                break
            if isinstance(base_lhs, JSONObject):
                current_type = "object"
            elif isinstance(base_lhs, JSONArray):
                current_type = "array"

        if not path and (
            force_text
            or getattr(node, "_function_context", False)
            or getattr(node, "is_ordering", False)
        ):
            sql = f"({sql})::text"
        if getattr(node, "_is_boolean_context", False):
            sql = (
                f"({sql}) IS NOT NULL"
                if getattr(node, "_negated", False)
                else f"({sql}) IS NULL"
            )
        return sql, lhs_params

    def _compile_cast(self, node):
        try:
            inner_expr = getattr(node, "expression", None)
            if inner_expr is None:
                inner_expr = (
                    node.source_expressions[0]
                    if getattr(node, "source_expressions", None)
                    else node
                )

            expr_sql, expr_params = super().compile(inner_expr)
        except Exception:
            return super().compile(node)

        db_type = None
        try:
            db_type = node.output_field.db_type(self.connection) or "varchar"
        except Exception:
            db_type = "varchar"

        invalid_cast_map = {
            "serial": "integer",
            "bigserial": "bigint",
            "smallserial": "smallint",
        }
        db_type = invalid_cast_map.get(db_type, db_type)
        sql = f"{expr_sql}::{db_type}"
        return sql, expr_params

    def _compile_has_key(self, node):
        lhs_sql, lhs_params = self.compile(node.lhs)
        params = lhs_params[:]

        key_expr = (
            getattr(node, "rhs", None)
            or getattr(node, "key", None)
            or getattr(node, "_key", None)
        )
        if key_expr is None:
            raise ValueError("Cannot determine key for HasKey node")

        if isinstance(key_expr, str):
            sql = f"{lhs_sql} ? %s"
            params.append(key_expr)
        else:
            key_sql, key_params = self.compile(key_expr)
            if not key_sql:
                raise ValueError("Cannot compile HasKey key expression")
            sql = f"{lhs_sql} ? ({key_sql})::text"
            params.extend(key_params)

        return sql, params

    def _compile_has_keys(self, node):
        lhs_sql, lhs_params = self.compile(node.lhs)
        params = lhs_params[:]

        keys = getattr(node, "rhs", None) or getattr(node, "keys", None)
        if not keys:
            raise ValueError("Cannot determine keys for HasKeys node")

        sql_parts = []
        for key_expr in keys:
            if isinstance(key_expr, str):
                sql_parts.append("%s")
                params.append(key_expr)
            else:
                key_sql, key_params = self.compile(key_expr)
                sql_parts.append(f"({key_sql})::text")
                params.extend(key_params)

        keys_sql = ", ".join(sql_parts)
        sql = f"{lhs_sql} ?& array[{keys_sql}]"
        return sql, params

    def _compile_has_any_keys(self, node):
        lhs_sql, lhs_params = self.compile(node.lhs)
        params = lhs_params[:]

        keys = getattr(node, "rhs", None) or getattr(node, "keys", None)
        if not keys:
            raise ValueError("Cannot determine keys for HasAnyKeys node")

        sql_parts = []
        for key_expr in keys:
            if isinstance(key_expr, str):
                sql_parts.append("%s")
                params.append(key_expr)
            else:
                key_sql, key_params = self.compile(key_expr)
                sql_parts.append(f"({key_sql})::text")
                params.extend(key_params)

        keys_sql = ", ".join(sql_parts)
        sql = f"{lhs_sql} ?| array[{keys_sql}]"
        return sql, params
