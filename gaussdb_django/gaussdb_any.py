import ipaddress
from functools import lru_cache

try:
    from gaussdb import ClientCursor, IsolationLevel, adapt, adapters, errors, sql
    from gaussdb import types
    from gaussdb.types.datetime import TimestamptzLoader
    from gaussdb.types.json import Jsonb
    from gaussdb.types.range import Range, RangeDumper
    from gaussdb.types.string import TextLoader

    Inet = ipaddress.ip_address

    DateRange = DateTimeRange = DateTimeTZRange = NumericRange = Range
    RANGE_TYPES = (Range,)

    TSRANGE_OID = "tsrange"
    TSTZRANGE_OID = "tstzrange"

    def mogrify(sql, params, connection):
        with connection.cursor() as cursor:
            return ClientCursor(cursor.connection).mogrify(sql, params)

    # Adapters.
    class BaseTzLoader(TimestamptzLoader):
        """
        Load a Gaussdb timestamptz using the a specific timezone.
        The timezone can be None too, in which case it will be chopped.
        """

        timezone = None

        def load(self, data):
            res = super().load(data)
            return res.replace(tzinfo=self.timezone)

    def register_tzloader(tz, context):
        class SpecificTzLoader(BaseTzLoader):
            timezone = tz

        context.adapters.register_loader("timestamptz", SpecificTzLoader)

    class DjangoRangeDumper(RangeDumper):
        """A Range dumper customized for Django."""

        def upgrade(self, obj, format):
            # Dump ranges containing naive datetimes as tstzrange, because
            # Django doesn't use tz-aware ones.
            dumper = super().upgrade(obj, format)
            if dumper is not self and dumper.oid == TSRANGE_OID:
                dumper.oid = TSTZRANGE_OID
            return dumper

    @lru_cache
    def get_adapters_template(use_tz, timezone):
        # Create at adapters map extending the base one.
        ctx = adapt.AdaptersMap(adapters)
        # Register a no-op dumper to avoid a round trip from gaussdb
        # decode to json.dumps() to json.loads(), when using a custom decoder
        # in JSONField.
        ctx.register_loader("jsonb", TextLoader)
        # Don't convert automatically from Gaussdb network types to Python
        # ipaddress.
        ctx.register_loader("inet", TextLoader)
        ctx.register_loader("cidr", TextLoader)
        ctx.register_dumper(Range, DjangoRangeDumper)
        # Register a timestamptz loader configured on self.timezone.
        # This, however, can be overridden by create_cursor.
        register_tzloader(timezone, ctx)
        return ctx

except ImportError as e:
    raise ImportError(f"Failed to import gaussdb module: {e}")
