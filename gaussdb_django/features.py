from django.db import DataError, InterfaceError
from django.db.backends.base.features import BaseDatabaseFeatures
from django.utils.functional import cached_property


class DatabaseFeatures(BaseDatabaseFeatures):
    minimum_database_version = (8,)
    allows_group_by_selected_pks = True
    can_return_columns_from_insert = True
    can_return_rows_from_bulk_insert = True
    has_real_datatype = True
    has_native_uuid_field = True
    has_native_duration_field = True
    has_native_json_field = True
    supports_json_array = True
    can_defer_constraint_checks = False
    has_select_for_update = True
    has_select_for_update_nowait = True
    has_select_for_update_of = True
    has_select_for_update_skip_locked = True
    has_select_for_no_key_update = False
    can_release_savepoints = True
    supports_comments = True
    supports_tablespaces = True
    supports_transactions = True
    can_introspect_materialized_views = False
    can_distinct_on_fields = True
    can_rollback_ddl = True
    schema_editor_uses_clientside_param_binding = True
    supports_combined_alters = True
    nulls_order_largest = True
    closed_cursor_error_class = InterfaceError
    greatest_least_ignores_nulls = True
    can_clone_databases = False
    supports_temporal_subtraction = True
    requires_literal_defaults = False
    supports_slicing_ordering_in_compound = True
    supports_default_keyword_in_bulk_insert = False
    supports_timezones = True
    allows_group_by_select_index = False
    supports_datefield_without_time = False
    supports_utc_datetime_cast = False
    supports_collations = True
    supports_index_descending = False
    create_test_procedure_without_params_sql = """
        CREATE FUNCTION test_procedure () RETURNS void AS $$
        DECLARE
            V_I INTEGER;
        BEGIN
            V_I := 1;
        END;
    $$ LANGUAGE plpgsql;"""
    create_test_procedure_with_int_param_sql = """
        CREATE FUNCTION test_procedure (P_I INTEGER) RETURNS void AS $$
        DECLARE
            V_I INTEGER;
        BEGIN
            V_I := P_I;
        END;
    $$ LANGUAGE plpgsql;"""
    requires_casted_case_in_updates = True
    supports_over_clause = True
    supports_frame_exclusion = True
    only_supports_unbounded_with_preceding_and_following = True
    supports_aggregate_filter_clause = False
    supports_deferrable_unique_constraints = True
    has_json_operators = True
    json_key_contains_list_matching_requires_list = True
    supports_update_conflicts = True
    supports_update_conflicts_with_target = True
    supports_covering_indexes = False
    supports_stored_generated_columns = True
    supports_stored_generated_columns_with_like = False
    supports_virtual_generated_columns = False
    can_rename_index = True
    is_postgresql_9_4 = False
    supports_multiple_alter_column = False
    supports_alter_column_to_serial = False
    supports_table_check_constraints = False
    supports_alter_field_with_to_field = False
    supports_default_empty_string_for_not_null = False
    supports_subquery_variable_references = False
    supports_isempty_lookup = False
    supports_json_field = True
    supports_json_object_function = True
    supports_date_cast = False
    supports_concat_null_to_empty = False
    supports_lpad_empty_string = False
    supports_repeat_empty_string = False
    supports_right_zero_length = False
    supports_expression_indexes = False
    supports_date_field_introspection = False
    supports_index_column_ordering = False
    supports_ignore_conflicts = True
    supports_restart_identity = False
    interprets_empty_strings_as_nulls = True
    supports_unicode_identifiers = False
    supports_select_for_update_with_limit = False
    supports_admin_deleted_objects = False
    supports_explaining_query_execution = False
    supports_column_check_constraints = False
    supports_partial_indexes = False
    supports_collation_on_charfield = True
    supports_collation_on_textfield = True
    supports_non_deterministic_collations = False
    supports_recursive_m2m = True
    supports_boolean_exists_lhs = False
    supports_jsonfield_check_constraints = False
    supports_json_field_contains = True
    supports_json_field_in_subquery = False
    supports_json_field_filter_clause = False
    supports_json_field_key_lookup = False
    supports_json_nested_key = False
    test_collations = {
        "deterministic": "C",
        "non_default": "sv_SE.utf8",
        "swedish_ci": "sv_SE.utf8",
        "virtual": "sv_SE.utf8",
    }
    test_now_utc_template = "STATEMENT_TIMESTAMP() AT TIME ZONE 'UTC'"
    insert_test_table_with_defaults = "INSERT INTO {} DEFAULT VALUES"

    @cached_property
    def django_test_skips(self):
        skips = {
            "opclasses are GaussDB only.": {
                "indexes.tests.SchemaIndexesNotGaussDBTests."
                "test_create_index_ignores_opclasses",
            },
            "GaussDB requires casting to text.": {
                "lookup.tests.LookupTests.test_textfield_exact_null",
            },
            "Oracle doesn't support SHA224.": {
                "db_functions.text.test_sha224.SHA224Tests.test_basic",
                "db_functions.text.test_sha224.SHA224Tests.test_transform",
            },
            "GaussDB doesn't correctly calculate ISO 8601 week numbering before "
            "1583 (the Gregorian calendar was introduced in 1582).": {
                "db_functions.datetime.test_extract_trunc.DateFunctionTests."
                "test_trunc_week_before_1000",
                "db_functions.datetime.test_extract_trunc."
                "DateFunctionWithTimeZoneTests.test_trunc_week_before_1000",
            },
            "GaussDB doesn't support bitwise XOR.": {
                "expressions.tests.ExpressionOperatorTests.test_lefthand_bitwise_xor",
                "expressions.tests.ExpressionOperatorTests."
                "test_lefthand_bitwise_xor_null",
                "expressions.tests.ExpressionOperatorTests."
                "test_lefthand_bitwise_xor_right_null",
            },
            "GaussDB requires ORDER BY in row_number, ANSI:SQL doesn't.": {
                "expressions_window.tests.WindowFunctionTests."
                "test_row_number_no_ordering",
                "prefetch_related.tests.PrefetchLimitTests.test_empty_order",
            },
            "GaussDB doesn't support changing collations on indexed columns (#33671).": {
                "migrations.test_operations.OperationTests."
                "test_alter_field_pk_fk_db_collation",
            },
            "GaussDB doesn't support comparing NCLOB to NUMBER.": {
                "generic_relations_regress.tests.GenericRelationTests."
                "test_textlink_filter",
            },
            "GaussDB doesn't support casting filters to NUMBER.": {
                "lookup.tests.LookupQueryingTests.test_aggregate_combined_lookup",
            },
        }
        if self.connection.settings_dict["OPTIONS"].get("pool"):
            skips.update(
                {
                    "Pool does implicit health checks": {
                        "backends.base.test_base.ConnectionHealthChecksTests."
                        "test_health_checks_enabled",
                        "backends.base.test_base.ConnectionHealthChecksTests."
                        "test_health_checks_enabled_errors_occurred",
                        "backends.base.test_base.ConnectionHealthChecksTests."
                        "test_health_checks_disabled",
                        "backends.base.test_base.ConnectionHealthChecksTests."
                        "test_set_autocommit_health_checks_enabled",
                        "servers.tests.LiveServerTestCloseConnectionTest."
                        "test_closes_connections",
                        "backends.oracle.tests.TransactionalTests."
                        "test_password_with_at_sign",
                    },
                }
            )
        if self.uses_server_side_binding:
            skips.update(
                {
                    "The actual query cannot be determined for server side bindings": {
                        "backends.base.test_base.ExecuteWrapperTests."
                        "test_wrapper_debug",
                    }
                },
            )
        return skips

    @cached_property
    def django_test_expected_failures(self):
        expected_failures = set()
        if self.uses_server_side_binding:
            expected_failures.update(
                {
                    # Parameters passed to expressions in SELECT and GROUP BY
                    # clauses are not recognized as the same values when using
                    # server-side binding cursors (#34255).
                    "aggregation.tests.AggregateTestCase."
                    "test_group_by_nested_expression_with_params",
                }
            )
        return expected_failures

    @cached_property
    def uses_server_side_binding(self):
        options = self.connection.settings_dict["OPTIONS"]
        return options.get("server_side_binding") is True

    @cached_property
    def prohibits_null_characters_in_text_exception(self):
        return DataError, "GaussDB text fields cannot contain NUL (0x00) bytes"

    @cached_property
    def introspected_field_types(self):
        return {
            **super().introspected_field_types,
            "GenericIPAddressField": "CharField",
            "PositiveBigIntegerField": "BigIntegerField",
            "PositiveIntegerField": "IntegerField",
            "PositiveSmallIntegerField": "IntegerField",
            "TimeField": "DateTimeField",
        }

    supports_unlimited_charfield = True
    supports_nulls_distinct_unique_constraints = False
