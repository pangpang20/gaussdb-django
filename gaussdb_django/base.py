"""
Gaussdb database backend for Django.

Requires gaussdb >= 1.0.3
"""
import asyncio
import threading
import warnings
from contextlib import contextmanager

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError as WrappedDatabaseError
from django.db import connections
from django.db.backends.base.base import NO_DB_ALIAS, BaseDatabaseWrapper
from django.db.backends.utils import (
    CursorDebugWrapper as BaseCursorDebugWrapper
)
from django.utils.asyncio import async_unsafe
from django.utils.functional import cached_property
from django.utils.version import get_version_tuple

try:
    try:
        import gaussdb as Database
    except ImportError:
        pass
except ImportError:
    raise ImproperlyConfigured("Error loading gaussdb module")

from .gaussdb_any import (
    IsolationLevel,
    get_adapters_template,
    register_tzloader,
)  # NOQA isort:skip
from gaussdb import adapters, sql
from gaussdb.pq import Format


def gaussdb_version():
    version = Database.__version__.split(" ", 1)[0]
    return get_version_tuple(version)


if gaussdb_version() < (1, 0, 3):
    raise ImproperlyConfigured(
        f"gaussdb version 1.0.3 or newer is required; you have {Database.__version__}"
    )

TIMESTAMPTZ_OID = adapters.types["timestamptz"].oid

# Some of these import gaussdb, so import them after checking if it's installed.
from .client import DatabaseClient  # NOQA isort:skip
from .creation import DatabaseCreation  # NOQA isort:skip
from .features import DatabaseFeatures  # NOQA isort:skip
from .introspection import DatabaseIntrospection  # NOQA isort:skip
from .operations import DatabaseOperations  # NOQA isort:skip
from .schema import DatabaseSchemaEditor  # NOQA isort:skip


def _get_varchar_column(data):
    if data["max_length"] is None:
        return "varchar"
    return "varchar(%(max_length)s)" % data


class DatabaseWrapper(BaseDatabaseWrapper):
    vendor = "gaussdb"
    display_name = "GaussDB"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # This dictionary maps Field objects to their associated Gaussdb column
    # types, as strings. Column-type strings can contain format strings; they'll
    # be interpolated against the values of Field.__dict__ before being output.
    # If a column type is set to None, it won't be included in the output.
    data_types = {
        "AutoField": "integer",
        "BigAutoField": "bigint",
        "BinaryField": "bytea",
        "BooleanField": "boolean",
        "CharField": _get_varchar_column,
        "DateField": "date",
        "DateTimeField": "timestamp with time zone",
        "DecimalField": "numeric(%(max_digits)s, %(decimal_places)s)",
        "DurationField": "interval",
        "FileField": "varchar(%(max_length)s)",
        "FilePathField": "varchar(%(max_length)s)",
        "FloatField": "double precision",
        "IntegerField": "integer",
        "BigIntegerField": "bigint",
        "IPAddressField": "inet",
        "GenericIPAddressField": "inet",
        "JSONField": "jsonb",
        "OneToOneField": "integer",
        "PositiveBigIntegerField": "bigint",
        "PositiveIntegerField": "integer",
        "PositiveSmallIntegerField": "smallint",
        "SlugField": "varchar(%(max_length)s)",
        "SmallAutoField": "smallint",
        "SmallIntegerField": "smallint",
        "TextField": "text",
        "TimeField": "time",
        "UUIDField": "uuid",
    }

    data_type_check_constraints = {
        "PositiveBigIntegerField": '"%(column)s" >= 0',
        "PositiveIntegerField": '"%(column)s" >= 0',
        "PositiveSmallIntegerField": '"%(column)s" >= 0',
    }
    data_types_suffix = {
        "AutoField": "",
        "BigAutoField": "",
        "SmallAutoField": "",
    }
    operators = {
        "exact": "= %s",
        "iexact": "= UPPER(%s)",
        "contains": "LIKE %s",
        "icontains": "LIKE UPPER(%s)",
        "regex": "~ %s",
        "iregex": "~* %s",
        "gt": "> %s",
        "gte": ">= %s",
        "lt": "< %s",
        "lte": "<= %s",
        "startswith": "LIKE %s",
        "endswith": "LIKE %s",
        "istartswith": "LIKE UPPER(%s)",
        "iendswith": "LIKE UPPER(%s)",
    }

    # The patterns below are used to generate SQL pattern lookup clauses when
    # the right-hand side of the lookup isn't a raw string (it might be an expression
    # or the result of a bilateral transformation).
    # In those cases, special characters for LIKE operators (e.g. \, *, _) should be
    # escaped on database side.
    #
    # Note: we use str.format() here for readability as '%' is used as a wildcard for
    # the LIKE operator.
    pattern_esc = (
        r"REPLACE(REPLACE(REPLACE({}, E'\\', E'\\\\'), E'%%', E'\\%%'), E'_', E'\\_')"
    )
    pattern_ops = {
        "contains": "LIKE '%%' || {} || '%%'",
        "icontains": "LIKE '%%' || UPPER({}) || '%%'",
        "startswith": "LIKE {} || '%%'",
        "istartswith": "LIKE UPPER({}) || '%%'",
        "endswith": "LIKE '%%' || {}",
        "iendswith": "LIKE '%%' || UPPER({})",
    }

    Database = Database
    SchemaEditorClass = DatabaseSchemaEditor
    # Classes instantiated in __init__().
    client_class = DatabaseClient
    creation_class = DatabaseCreation
    features_class = DatabaseFeatures
    introspection_class = DatabaseIntrospection
    ops_class = DatabaseOperations
    # Gaussdb backend-specific attributes.
    _named_cursor_idx = 0
    _connection_pools = {}

    @property
    def pool(self):
        pool_options = self.settings_dict["OPTIONS"].get("pool")
        if self.alias == NO_DB_ALIAS or not pool_options:
            return None

        if self.alias not in self._connection_pools:
            if self.settings_dict.get("CONN_MAX_AGE", 0) != 0:
                raise ImproperlyConfigured(
                    "Pooling doesn't support persistent connections."
                )
            # Set the default options.
            if pool_options is True:
                pool_options = {}

            try:
                from gaussdb_pool import ConnectionPool
            except ImportError as err:
                raise ImproperlyConfigured(
                    "Error loading gaussdb_pool module.\nDid you install gaussdb[pool]?"
                ) from err

            connect_kwargs = self.get_connection_params()
            # Ensure we run in autocommit, Django properly sets it later on.
            connect_kwargs["autocommit"] = True
            enable_checks = self.settings_dict["CONN_HEALTH_CHECKS"]
            pool = ConnectionPool(
                kwargs=connect_kwargs,
                open=False,  # Do not open the pool during startup.
                configure=self._configure_connection,
                check=ConnectionPool.check_connection if enable_checks else None,
                **pool_options,
            )
            # setdefault() ensures that multiple threads don't set this in
            # parallel. Since we do not open the pool during it's init above,
            # this means that at worst during startup multiple threads generate
            # pool objects and the first to set it wins.
            self._connection_pools.setdefault(self.alias, pool)

        return self._connection_pools[self.alias]

    def close_pool(self):
        if self.pool:
            self.pool.close()
            del self._connection_pools[self.alias]

    def get_database_version(self):
        """
        Return a tuple of the database's version.
        E.g. for pg_version 120004, return (12, 4).
        """
        return divmod(self.pg_version, 10000)

    def get_connection_params(self):
        settings_dict = self.settings_dict
        # None may be used to connect to the default 'gaussdb' db
        if settings_dict["NAME"] == "" and not settings_dict["OPTIONS"].get("service"):
            raise ImproperlyConfigured(
                "settings.DATABASES is improperly configured. "
                "Please supply the NAME or OPTIONS['service'] value."
            )
        if len(settings_dict["NAME"] or "") > self.ops.max_name_length():
            raise ImproperlyConfigured(
                "The database name '%s' (%d characters) is longer than "
                "Gaussdb's limit of %d characters. Supply a shorter NAME "
                "in settings.DATABASES."
                % (
                    settings_dict["NAME"],
                    len(settings_dict["NAME"]),
                    self.ops.max_name_length(),
                )
            )
        if settings_dict["NAME"]:
            conn_params = {
                "dbname": settings_dict["NAME"],
                **settings_dict["OPTIONS"],
            }
        elif settings_dict["NAME"] is None:
            # Connect to the default 'postgres' db.
            settings_dict["OPTIONS"].pop("service", None)
            conn_params = {"dbname": "postgres", **settings_dict["OPTIONS"]}
        else:
            conn_params = {**settings_dict["OPTIONS"]}
        conn_params["client_encoding"] = "UTF8"

        conn_params.pop("assume_role", None)
        conn_params.pop("isolation_level", None)

        pool_options = conn_params.pop("pool", None)
        if pool_options:
            raise ImproperlyConfigured("Database pooling requires gaussdb >= 1.0.3")

        server_side_binding = conn_params.pop("server_side_binding", None)
        conn_params.setdefault(
            "cursor_factory",
            (ServerBindingCursor if server_side_binding is True else Cursor),
        )
        if settings_dict["USER"]:
            conn_params["user"] = settings_dict["USER"]
        if settings_dict["PASSWORD"]:
            conn_params["password"] = settings_dict["PASSWORD"]
        if settings_dict["HOST"]:
            conn_params["host"] = settings_dict["HOST"]
        if settings_dict["PORT"]:
            conn_params["port"] = settings_dict["PORT"]
        conn_params["context"] = get_adapters_template(settings.USE_TZ, self.timezone)
        # Disable prepared statements by default to keep connection poolers
        # working. Can be reenabled via OPTIONS in the settings dict.
        conn_params["prepare_threshold"] = conn_params.pop("prepare_threshold", None)
        return conn_params

    @async_unsafe
    def get_new_connection(self, conn_params):
        # self.isolation_level must be set:
        # - after connecting to the database in order to obtain the database's
        #   default when no value is explicitly specified in options.
        # - before calling _set_autocommit() because if autocommit is on, that
        #   will set connection.isolation_level to ISOLATION_LEVEL_AUTOCOMMIT.
        options = self.settings_dict["OPTIONS"]
        set_isolation_level = False
        try:
            isolation_level_value = options["isolation_level"]
        except KeyError:
            self.isolation_level = IsolationLevel.READ_COMMITTED
        else:
            # Set the isolation level to the value from OPTIONS.
            try:
                self.isolation_level = IsolationLevel(isolation_level_value)
                set_isolation_level = True
            except ValueError:
                raise ImproperlyConfigured(
                    f"Invalid transaction isolation level {isolation_level_value} "
                    f"specified. Use one of the gaussdb.IsolationLevel values."
                )
        if self.pool:
            # If nothing else has opened the pool, open it now.
            self.pool.open()
            connection = self.pool.getconn()
        else:
            connection = self.Database.connect(**conn_params)
        if set_isolation_level:
            connection.isolation_level = self.isolation_level
        return connection

    def ensure_timezone(self):
        # Close the pool so new connections pick up the correct timezone.
        self.close_pool()
        if self.connection is None:
            return False
        return self._configure_timezone(self.connection)

    def _configure_timezone(self, connection):
        conn_timezone_name = connection.info.parameter_status("TimeZone")
        timezone_name = self.timezone_name or "UTC"
        if not conn_timezone_name or conn_timezone_name != timezone_name:
            with connection.cursor() as cursor:
                cursor.execute(self.ops.set_time_zone_sql(), [timezone_name])
            return True
        return False

    def _configure_role(self, connection):
        if new_role := self.settings_dict["OPTIONS"].get("assume_role"):
            with connection.cursor() as cursor:
                sql = self.ops.compose_sql("SET ROLE %s", [new_role])
                cursor.execute(sql)
            return True
        return False

    def _configure_connection(self, connection):
        # This function is called from init_connection_state and from the
        # gaussdb pool itself after a connection is opened.

        # Commit after setting the time zone.
        commit_tz = self._configure_timezone(connection)
        # Set the role on the connection. This is useful if the credential used
        # to login is not the same as the role that owns database resources. As
        # can be the case when using temporary or ephemeral credentials.
        commit_role = self._configure_role(connection)

        return commit_role or commit_tz

    def _close(self):
        if self.connection is not None:
            # `wrap_database_errors` only works for `putconn` as long as there
            # is no `reset` function set in the pool because it is deferred
            # into a thread and not directly executed.
            with self.wrap_database_errors:
                if self.pool:
                    # Ensure the correct pool is returned. This is a workaround
                    # for tests so a pool can be changed on setting changes
                    # (e.g. USE_TZ, TIME_ZONE).
                    self.connection._pool.putconn(self.connection)
                    # Connection can no longer be used.
                    self.connection = None
                else:
                    return self.connection.close()

    def init_connection_state(self):
        super().init_connection_state()

        if self.connection is not None and not self.pool:
            commit = self._configure_connection(self.connection)

            if commit and not self.get_autocommit():
                self.connection.commit()

        if self.supports_identity_columns():
            # Use identity (for GaussDB)
            pass
        else:
            # Fall back to serial (for openGauss)
            self.data_types["AutoField"] = "serial"
            self.data_types["BigAutoField"] = "bigserial"
            self.data_types["SmallAutoField"] = "smallserial"
            self.data_types_suffix = {}

    def supports_identity_columns(self):
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TEMPORARY TABLE test_identity_support (
                        id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY
                    )
                """
                )
                cursor.execute("DROP TABLE test_identity_support")
                return True
        except Exception:
            # If syntax error or unsupported, assume no identity support
            return False

    @async_unsafe
    def create_cursor(self, name=None):
        if name:
            if self.settings_dict["OPTIONS"].get("server_side_binding") is not True:
                # gaussdb >= 1.0.3 forces the usage of server-side bindings for
                # named cursors so a specialized class that implements
                # server-side cursors while performing client-side bindings
                # must be used if `server_side_binding` is disabled (default).
                cursor = ServerSideCursor(
                    self.connection,
                    name=name,
                    scrollable=False,
                    withhold=self.connection.autocommit,
                )
            else:
                # In autocommit mode, the cursor will be used outside of a
                # transaction, hence use a holdable cursor.
                cursor = self.connection.cursor(
                    name, scrollable=False, withhold=self.connection.autocommit
                )
        else:
            cursor = self.connection.cursor()

        tzloader = self.connection.adapters.get_loader(TIMESTAMPTZ_OID, Format.TEXT)
        if self.timezone != tzloader.timezone:
            register_tzloader(self.timezone, cursor)

        return cursor

    def tzinfo_factory(self, offset):
        return self.timezone

    @async_unsafe
    def chunked_cursor(self):
        self._named_cursor_idx += 1
        # Get the current async task
        # Note that right now this is behind @async_unsafe, so this is
        # unreachable, but in future we'll start loosening this restriction.
        # For now, it's here so that every use of "threading" is
        # also async-compatible.
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        # Current task can be none even if the current_task call didn't error
        if current_task:
            task_ident = str(id(current_task))
        else:
            task_ident = "sync"
        # Use that and the thread ident to get a unique name
        return self._cursor(
            name="_django_curs_%d_%s_%d"
            % (
                # Avoid reusing name in other threads / tasks
                threading.current_thread().ident,
                task_ident,
                self._named_cursor_idx,
            )
        )

    def _set_autocommit(self, autocommit):
        with self.wrap_database_errors:
            self.connection.autocommit = autocommit

    def check_constraints(self, table_names=None):
        """
        Check constraints by setting them to immediate. Return them to deferred
        afterward.
        """
        with self.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")

    def is_usable(self):
        if self.connection is None:
            return False
        try:
            # Use a gaussdb cursor directly, bypassing Django's utilities.
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Database.Error:
            return False
        else:
            return True

    def close_if_health_check_failed(self):
        if self.pool:
            # The pool only returns healthy connections.
            return
        return super().close_if_health_check_failed()

    @contextmanager
    def _nodb_cursor(self):
        cursor = None
        try:
            with super()._nodb_cursor() as cursor:
                yield cursor
        except (Database.DatabaseError, WrappedDatabaseError):
            if cursor is not None:
                raise
            warnings.warn(
                "Normally Django will use a connection to the 'postgres' database "
                "to avoid running initialization queries against the production "
                "database when it's not needed (for example, when running tests). "
                "Django was unable to create a connection to the 'postgres' database "
                "and will use the first Gaussdb database instead.",
                RuntimeWarning,
            )
            for connection in connections.all():
                if (
                    connection.vendor == "gaussdb"
                    and connection.settings_dict["NAME"] != "postgres"
                ):
                    conn = self.__class__(
                        {
                            **self.settings_dict,
                            "NAME": connection.settings_dict["NAME"],
                        },
                        alias=self.alias,
                    )
                    try:
                        with conn.cursor() as cursor:
                            yield cursor
                    finally:
                        conn.close()
                    break
            else:
                raise

    @cached_property
    def pg_version(self):
        with self.temporary_connection():
            return self.connection.info.server_version

    def check_database_version_supported(self):
        """
        Override Django's version check to support GaussDB.
        GaussDB reports version like 9.204 but is PostgreSQL-compatible.
        """
        try:
            with self.temporary_connection() as conn:
                server_version = conn.execute("select version()").fetchall()[0][0]
                print(f"Server Version String: {server_version}")
                if server_version:
                    self.pg_version = 140000
                    return
        except Exception as e:
            raise Database.Error(
                f"Unable to determine server version from server_version parameter: {e}"
            )

    def make_debug_cursor(self, cursor):
        return CursorDebugWrapper(cursor, self)


class CursorMixin:
    """
    A subclass of gaussdb cursor implementing callproc.
    """

    def callproc(self, name, args=None):
        if not isinstance(name, sql.Identifier):
            name = sql.Identifier(name)

        qparts = [sql.SQL("SELECT * FROM "), name, sql.SQL("(")]
        if args:
            for item in args:
                qparts.append(sql.Literal(item))
                qparts.append(sql.SQL(","))
            del qparts[-1]

        qparts.append(sql.SQL(")"))
        stmt = sql.Composed(qparts)
        self.execute(stmt)
        return args


class ServerBindingCursor(CursorMixin, Database.Cursor):
    pass


class Cursor(CursorMixin, Database.ClientCursor):
    pass


class ServerSideCursor(
    CursorMixin, Database.client_cursor.ClientCursorMixin, Database.ServerCursor
):
    """
    gaussdb >= 1.0.3 forces the usage of server-side bindings when using named
    cursors but the ORM doesn't yet support the systematic generation of
    prepareable SQL (#20516).

    ClientCursorMixin forces the usage of client-side bindings while
    ServerCursor implements the logic required to declare and scroll
    through named cursors.

    Mixing ClientCursorMixin in wouldn't be necessary if Cursor allowed to
    specify how parameters should be bound instead, which ServerCursor
    would inherit, but that's not the case.
    """


class CursorDebugWrapper(BaseCursorDebugWrapper):
    def copy(self, statement):
        with self.debug_sql(statement):
            return self.cursor.copy(statement)
