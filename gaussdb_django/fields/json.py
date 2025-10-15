import json
from django.db.models import JSONField as DjangoJSONField

class GaussDBJSONField(DjangoJSONField):
    def from_db_value(self, value, expression, connection):
        if isinstance(value, (dict, list)) or value is None:
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
