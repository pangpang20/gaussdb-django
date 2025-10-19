from django.db.models import Func


class GaussArraySubscript(Func):
    function = ""
    template = "%(expressions)s->%(index)s"

    def __init__(self, expression, index, **extra):
        super().__init__(expression, **extra)
        self.index = index
