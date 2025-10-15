from django.db.models.sql.compiler import (
    SQLAggregateCompiler,
    SQLCompiler,
    SQLDeleteCompiler,
)
from django.db.models.sql.compiler import SQLInsertCompiler as BaseSQLInsertCompiler
from django.db.models.sql.compiler import SQLUpdateCompiler
from django.db.models.sql.compiler import SQLCompiler as BaseSQLCompiler
from django.db.models.functions import JSONArray, JSONObject
from django.db.models import JSONField, IntegerField, FloatField


__all__ = [
    "SQLAggregateCompiler",
    "SQLCompiler",
    "SQLDeleteCompiler",
    "SQLInsertCompiler",
    "SQLUpdateCompiler",
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
    def compile(self, node, force_text=True):
        if node.__class__.__name__ == 'OrderBy':
            node.expression.is_ordering = True

        if isinstance(node, JSONArray):
            return self._compile_json_array(node)

        elif isinstance(node, JSONObject):
            return self._compile_json_object(node)

        elif node.__class__.__name__ == 'KeyTransform':
            return self._compile_key_transform(node, force_text=force_text)
        elif node.__class__.__name__ == 'Cast':
            return self._compile_cast(node)
        elif node.__class__.__name__ == 'HasKey':
            return self._compile_has_key(node)
        elif node.__class__.__name__ == 'HasKeys':
            return self._compile_has_keys(node)
        elif node.__class__.__name__ == 'HasAnyKeys':
            return self._compile_has_any_keys(node)

        return super().compile(node)

    def _compile_json_array(self, node):
        if not node.source_expressions:
            return "'[]'::json", []
        params = []
        sql_params = []
        for arg in node.source_expressions:
            arg_sql, arg_params = self.compile(arg)
            if not arg_sql:
                raise ValueError(f"Cannot compile argument {arg} to SQL")
            sql_params.append(arg_sql)
            params.extend(arg_params)

        sql = f"json_build_array({', '.join(sql_params)})"
        return sql, params

    def _compile_json_object(self, node):
        expressions = node.source_expressions
        if not expressions:
            return "'{}'::json", []
        sql_params = []
        params = []
        if len(expressions) % 2 != 0:
            raise ValueError("JSONObject requires even number of arguments (key-value pairs)")
        for i in range(0, len(expressions), 2):
            key_sql, key_params = self.compile(expressions[i])
            value_sql, value_params = self.compile(expressions[i + 1])
            if not key_sql or not value_sql:
                raise ValueError(f"Cannot compile key/value pair: {expressions[i]}, {expressions[i+1]}")
            sql_params.append(f"{key_sql}, {value_sql}")
            params.extend(key_params + value_params)
        sql = f"json_build_object({', '.join(sql_params)})"
        return sql, params

    def _compile_key_transform(self, node, force_text=False):
        def collect_path(n):
            path = []
            while n.__class__.__name__ == 'KeyTransform':
                key_expr = getattr(n, 'key', None) or getattr(n, 'path', None) or getattr(n, '_key', None)
                lhs = n.lhs

                if isinstance(lhs, JSONObject) and key_expr is None:
                    key_node = lhs.source_expressions[0]
                    key_expr = getattr(key_node, 'value', key_node)

                if key_expr is None:
                    if lhs.__class__.__name__ == 'KeyTransform':
                        lhs, sub_path = collect_path(lhs)
                        path.extend(sub_path)
                        n = lhs
                        continue
                    else:
                        return lhs, path

                path.append(key_expr)
                n = lhs

            return n, path

        base_lhs, path = collect_path(node)
        print("DEBUG: base_lhs:", base_lhs, "type:", type(base_lhs))
        print("DEBUG: path:", path)
        print("DEBUG: node.output_field type:", type(node.output_field))
        print("DEBUG: is_ordering:", getattr(node, "is_ordering", False))
        print("DEBUG: force_text:", force_text)

        if isinstance(base_lhs, JSONObject):
            lhs_sql, lhs_params = self._compile_json_object(base_lhs)
        elif isinstance(base_lhs, JSONArray):
            lhs_sql, lhs_params = self._compile_json_array(base_lhs)
        else:
            lhs_sql, lhs_params = super().compile(base_lhs)


        numeric_fields = (IntegerField, FloatField)
        is_ordering = getattr(node, "is_ordering", False)
        output_field = getattr(node, "output_field", None)

        if is_ordering and isinstance(base_lhs, (JSONObject, JSONArray)) and not path:
            lhs_sql = f"({lhs_sql})::text"

        sql = lhs_sql
        for k in path[:-1]:
            sql = f"{sql}->'{k}'"

        last_key = path[-1] if path else None

        if last_key is not None:
            if is_ordering:
                if isinstance(output_field, numeric_fields):
                    sql = f"({sql}->>'{last_key}')::numeric"
                else:
                    sql = f"({sql}->>'{last_key}')::text"
            else:
                if isinstance(output_field, numeric_fields):
                    sql = f"({sql}->>'{last_key}')::numeric"
                elif force_text:
                    sql = f"({sql}->>'{last_key}')::text"
                else:
                    sql = f"{sql}->'{last_key}'"
        else:
            if isinstance(base_lhs, (JSONObject, JSONArray)):
                if is_ordering or force_text:
                    sql = f"({sql})::text"
            else:
                sql = lhs_sql

        if getattr(node, "_is_boolean_context", False):
            sql = f"({sql}) IS NOT NULL" if getattr(node, "_negated", False) else f"({sql}) IS NULL"
        print("DEBUG: final sql:", sql)
        return sql, lhs_params


    def _compile_cast(self, node):
        try:
            inner_expr = getattr(node, "expression", None)
            if inner_expr is None and hasattr(node, "source_expressions"):
                inner_expr = node.source_expressions[0]

            expr_sql, expr_params = super().compile(inner_expr)
        except Exception as e:
            return super().compile(node)

        db_type = None
        try:
            db_type = node.output_field.db_type(self.connection) or "varchar"
        except Exception:
            db_type = 'varchar'

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

        key_expr = getattr(node, 'rhs', None) or getattr(node, 'key', None) or getattr(node, '_key', None)
        if key_expr is None:
            raise ValueError("Cannot determine key for HasKey node")

        if isinstance(key_expr, str):
            sql = f"{lhs_sql} ? %s"
            params.append(key_expr)
        else:
            key_sql, key_params = self.compile(key_expr)
            sql = f"{lhs_sql} ? ({key_sql})::text"
            params.extend(key_params)

        return sql, params


    def _compile_has_keys(self, node):
        lhs_sql, lhs_params = self.compile(node.lhs)
        params = lhs_params[:]

        keys = getattr(node, 'rhs', None) or getattr(node, 'keys', None)
        if not keys:
            raise ValueError("Cannot determine keys for HasKeys node")

        sql_parts = []
        for key_expr in keys:
            if isinstance(key_expr, str):
                sql_parts.append('%s')
                params.append(key_expr)
            else:
                key_sql, key_params = self.compile(key_expr)
                sql_parts.append(f"({key_sql})::text")
                params.extend(key_params)

        keys_sql = ', '.join(sql_parts)
        sql = f"{lhs_sql} ?& array[{keys_sql}]"
        return sql, params


    def _compile_has_any_keys(self, node):
        lhs_sql, lhs_params = self.compile(node.lhs)
        params = lhs_params[:]

        keys = getattr(node, 'rhs', None) or getattr(node, 'keys', None)
        if not keys:
            raise ValueError("Cannot determine keys for HasAnyKeys node")

        sql_parts = []
        for key_expr in keys:
            if isinstance(key_expr, str):
                sql_parts.append('%s')
                params.append(key_expr)
            else:
                key_sql, key_params = self.compile(key_expr)
                sql_parts.append(f"({key_sql})::text")
                params.extend(key_params)

        keys_sql = ', '.join(sql_parts)
        sql = f"{lhs_sql} ?| array[{keys_sql}]"
        return sql, params
