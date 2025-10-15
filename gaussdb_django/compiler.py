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
        params = []
        sql_params = []
        for arg in node.source_expressions:
            arg_sql, arg_params = self.compile(arg)
            sql_params.append(arg_sql)
            params.extend(arg_params)

        sql = f"json_build_array({', '.join(sql_params)})"
        return sql, params

    def _compile_json_object(self, node):
        sql_params = []
        params = []
        expressions = node.source_expressions
        if len(expressions) % 2 != 0:
            raise ValueError("JSONObject requires even number of arguments (key-value pairs)")
        for i in range(0, len(expressions), 2):
            key_sql, key_params = self.compile(expressions[i])
            value_sql, value_params = self.compile(expressions[i + 1])
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
                    if hasattr(key_node, 'value'):
                        key_expr = key_node.value
                    else:
                        key_expr = key_node

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

        if isinstance(base_lhs, JSONObject):
            lhs_sql, lhs_params = self._compile_json_object(base_lhs)
        elif isinstance(base_lhs, JSONArray):
            lhs_sql, lhs_params = self._compile_json_array(base_lhs)
        else:
            lhs_sql, lhs_params = super().compile(base_lhs)

        sql = lhs_sql
        for k in reversed(path):
            sql = f"{sql}->'{k}'"

        numeric_fields = (IntegerField, FloatField)
        if force_text or getattr(node, "is_ordering", False):
            sql = f"({sql})::text"
        elif isinstance(node.output_field, JSONField):
            sql = sql
        elif isinstance(node.output_field, numeric_fields):
            sql = f"({sql})::numeric"
        else:
            sql = f"({sql})::text"

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
