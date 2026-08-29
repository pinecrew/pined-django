import dj_database_url
from pydantic import BaseModel, model_serializer


class Database(BaseModel):
    """
    Connection parameters of a single database.

    Fields mirror the arguments of `dj_database_url.parse`, which turns
    them into Django's own shape at serialization time.
    """

    url: str
    engine: str | None = None
    conn_max_age: int | None = 0
    conn_health_checks: bool = False
    disable_server_side_cursors: bool = False
    ssl_require: bool = False
    test_options: dict | None = None

    @model_serializer
    def serialize(self) -> dj_database_url.DBConfig:
        return dj_database_url.parse(**dict(self))
