from django.db.models.sql.compiler import (
    SQLAggregateCompiler,
    SQLCompiler,
    SQLDeleteCompiler,
)
from django.db.models.sql.compiler import SQLInsertCompiler as BaseSQLInsertCompiler
from django.db.models.sql.compiler import SQLUpdateCompiler
from django.db.models.sql.compiler import SQLCompiler as BaseSQLCompiler
from django.db.models.functions import JSONArray, JSONObject
# from .expressions import GaussArraySubscript

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
        if isinstance(node, JSONArray):
            return self._compile_json_array(node)

        elif isinstance(node, JSONObject):
            return self._compile_json_object(node)

        elif node.__class__.__name__ == 'KeyTransform':
            return self._compile_key_transform(node, force_text=force_text)

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
                        raise ValueError(f"Cannot determine JSON key for {n}")

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

        if force_text:
            sql = f"({sql})::text"

        return sql, lhs_params
