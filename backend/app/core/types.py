"""Portable column types so the same models run on PostgreSQL (prod) and SQLite (tests)."""

import uuid

from sqlalchemy import CHAR, types
from sqlalchemy.dialects.postgresql import JSONB, UUID


class GUID(types.TypeDecorator):
    """UUID column: native ``uuid`` on PostgreSQL, ``CHAR(32)`` hex elsewhere."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return value
        return value.hex

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class JSONType(types.TypeDecorator):
    """JSONB on PostgreSQL, generic JSON elsewhere."""

    impl = types.JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(types.JSON())
